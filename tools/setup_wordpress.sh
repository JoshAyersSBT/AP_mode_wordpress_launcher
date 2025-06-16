#!/bin/bash

# setup_wordpress.sh
# Installs and configures WordPress on Raspberry Pi using Apache and MariaDB

set -e

DB_NAME=wordpress
DB_USER=wordpress
DB_PASS=wordpresspass
WP_DIR="/var/www/html"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Downloading latest WordPress..."
wget -q https://wordpress.org/latest.tar.gz -O /tmp/latest.tar.gz
tar -xzf /tmp/latest.tar.gz -C /tmp/
sudo rm -rf ${WP_DIR:?}/*
sudo cp -r /tmp/wordpress/* "$WP_DIR"
sudo chown -R www-data:www-data "$WP_DIR"
sudo chmod -R 755 "$WP_DIR"

log "Creating WordPress database and user..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME};"
sudo mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

log "Configuring wp-config.php..."
cp "${WP_DIR}/wp-config-sample.php" "${WP_DIR}/wp-config.php"
sed -i "s/database_name_here/${DB_NAME}/" "${WP_DIR}/wp-config.php"
sed -i "s/username_here/${DB_USER}/" "${WP_DIR}/wp-config.php"
sed -i "s/password_here/${DB_PASS}/" "${WP_DIR}/wp-config.php"

log "WordPress setup complete. Accessible via http://192.168.4.1"
