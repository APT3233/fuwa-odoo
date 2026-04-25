"""
Deploy Odoo custom modules lên server production.

Usage:
    python deploy.py <module>          # deploy nguyên module
    python deploy.py <module> --update # deploy + chạy -u (cập nhật DB schema)

Module hợp lệ:
    field_attendance   (chấm công)
    msc                (msc_performance)
    project            (custom_project)
    zkteco             (zkteco_attendance)
    hr                 (custom_hr)

SSH password đọc từ env SSH_PASSWORD, hoặc prompt khi chạy.
"""
import getpass
import os
import sys
import tarfile
import tempfile

import paramiko

# ── Config ────────────────────────────────────────────────────────────────────
HOST = "103.37.60.195"
PORT = 2222
USER = "devops"
DB   = "odoo_db"
LOCAL_BASE  = r"F:\odoo\odoo"
REMOTE_BASE = "/opt/prod-app/fuwa/odoo"
ODOO_BIN    = f"{REMOTE_BASE}/odoo-bin"
ODOO_CONF   = "/var/www/ql.fuwa.com.vn/config/odoo.conf"
PYTHON      = "/usr/bin/python3.11"

MODULE_MAP = {
    "field_attendance": "field_attendance",
    "msc":              "msc_performance",
    "project":          "custom_project",
    "zkteco":           "zkteco_attendance",
    "hr":               "custom_hr",
}


# ── SSH helpers ───────────────────────────────────────────────────────────────
def connect(password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=HOST, port=PORT, username=USER, password=password,
        timeout=30, look_for_keys=False, allow_agent=False,
    )
    return client


def run(ssh: paramiko.SSHClient, cmd: str, silent: bool = False) -> tuple[str, str]:
    print(f"  $ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if not silent:
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print("[err]", err.rstrip())
    return out, err


# ── Deploy ────────────────────────────────────────────────────────────────────
def make_tarball(module_dir: str, module_name: str) -> str:
    tmp = os.path.join(tempfile.gettempdir(), f"{module_name}.tar.gz")
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(module_dir, arcname=module_name)
    size_kb = os.path.getsize(tmp) // 1024
    print(f"  Packed {module_name}/ → {tmp} ({size_kb} KB)")
    return tmp


def deploy_module(ssh: paramiko.SSHClient, module_name: str, do_update: bool):
    local_dir = os.path.join(LOCAL_BASE, "custom_addons", module_name)
    if not os.path.isdir(local_dir):
        print(f"ERROR: local dir not found: {local_dir}")
        sys.exit(1)

    remote_addon_dir = f"{REMOTE_BASE}/custom_addons/{module_name}"
    remote_tar       = f"/tmp/{module_name}.tar.gz"

    # 1. Pack
    print("\n[1/3] Packing module...")
    local_tar = make_tarball(local_dir, module_name)

    # 2. Upload & extract
    print("\n[2/3] Uploading and extracting on server...")
    sftp = ssh.open_sftp()
    sftp.put(local_tar, remote_tar)
    sftp.close()

    run(ssh,
        f"sudo rm -rf {remote_addon_dir} && "
        f"sudo tar xzf {remote_tar} -C {REMOTE_BASE}/custom_addons/ && "
        f"sudo chown -R odoo:odoo {remote_addon_dir}"
    )

    # 3. Update DB schema (optional) + restart
    if do_update:
        print("\n[3/3] Stopping Odoo, upgrading module, restarting...")
        run(ssh, "sudo systemctl stop odoo")
        run(ssh,
            f"sudo -u odoo {PYTHON} {ODOO_BIN} "
            f"-c {ODOO_CONF} -d {DB} -u {module_name} "
            f"--stop-after-init --no-http 2>&1 | tail -30"
        )
        run(ssh, "sudo systemctl start odoo")
    else:
        print("\n[3/3] Restarting Odoo...")
        run(ssh, "sudo systemctl restart odoo")

    # Verify
    print()
    run(ssh,
        f'sudo -u postgres psql -d {DB} -t -c '
        f'"SELECT name, state, latest_version FROM ir_module_module '
        f'WHERE name=\'{module_name}\';"'
    )
    run(ssh, "sudo systemctl status odoo --no-pager | head -5")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    alias = args[0]
    do_update = "--update" in args

    if alias not in MODULE_MAP:
        print(f"Unknown module '{alias}'. Valid: {', '.join(MODULE_MAP)}")
        sys.exit(1)

    module_name = MODULE_MAP[alias]
    print(f"=== Deploy: {module_name} | update={do_update} ===")

    password = os.environ.get("SSH_PASSWORD") or getpass.getpass(f"Password for {USER}@{HOST}:{PORT}: ")

    print(f"\nConnecting to {USER}@{HOST}:{PORT}...")
    ssh = connect(password)
    print("Connected.\n")

    try:
        deploy_module(ssh, module_name, do_update)
    finally:
        ssh.close()

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
