FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for Odoo + common Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libxml2-dev \
    libxslt1-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    libx11-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo

COPY requirements.txt /opt/odoo/requirements.txt
RUN pip install --upgrade pip \
 && pip install "setuptools==68.2.2" "wheel==0.46.3" "setuptools_scm==10.0.2" \
 && pip install --no-build-isolation -r /opt/odoo/requirements.txt

COPY . /opt/odoo

EXPOSE 8069

CMD ["python", "odoo-bin", "-d", "odoo19", "-i", "base", "--addons-path=/opt/odoo/addons,/opt/odoo/odoo/addons", "--db_host=db", "--db_port=5432", "--db_user=odoo", "--db_password=odoo"]
