#!/bin/bash
# scripts/deploy-h5-site.sh
# H5 站点一键部署脚本（Nginx + Certbot + 反向代理 + SSL）
# 用法: ./deploy-h5-site.sh <site_key> <domain> <backend_ip> <email>
#
# 示例:
#   ./deploy-h5-site.sh wechat-01 h5-wechat.example.com 192.168.1.100 admin@example.com
#
# 前置条件:
#   - Ubuntu/Debian 服务器
#   - root 或 sudo 权限
#   - 域名 DNS 已解析到本服务器 IP
#   - 防火墙已开放 80 和 443 端口

set -euo pipefail

SITE_KEY=$1
DOMAIN=$2
BACKEND_IP=$3
EMAIL=$4

if [ -z "$SITE_KEY" ] || [ -z "$DOMAIN" ] || [ -z "$BACKEND_IP" ] || [ -z "$EMAIL" ]; then
  echo "用法: $0 <site_key> <domain> <backend_ip> <email>"
  echo "示例: $0 wechat-01 h5-wechat.example.com 192.168.1.100 admin@example.com"
  exit 1
fi

echo "=========================================="
echo "  H5 站点一键部署"
echo "=========================================="
echo "站点 Key:    $SITE_KEY"
echo "域名:        $DOMAIN"
echo "后端 IP:     $BACKEND_IP"
echo "SSL 邮箱:    $EMAIL"
echo "=========================================="
echo ""

# ─── 1. 安装依赖 ────────────────────────────────────────────────────────────
echo "[1/10] 安装 Nginx / Certbot / 基础工具..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx curl wget libapache2-mod-security2 modsecurity-crs
echo "  ✅ 依赖安装完成"
echo ""

# ─── 2. 配置 ModSecurity WAF ────────────────────────────────────────────────
echo "[2/10] 配置 ModSecurity WAF..."
cp /etc/modsecurity/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
sed -i 's/SecRuleEngine DetectionOnly/SecRuleEngine On/' /etc/modsecurity/modsecurity.conf
echo "  ✅ ModSecurity WAF 已启用"
echo ""

# ─── 3. 创建站点目录 ────────────────────────────────────────────────────────
echo "[3/10] 创建站点目录..."
mkdir -p "/var/www/${SITE_KEY}"
mkdir -p "/var/log/nginx/${SITE_KEY}"
echo "  ✅ 站点目录: /var/www/${SITE_KEY}"
echo "  ✅ 日志目录: /var/log/nginx/${SITE_KEY}"
echo ""

# ─── 4. 配置 Nginx server block + ModSecurity + 限流 ────────────────
echo "[4/10] 配置 Nginx server block + ModSecurity + 限流..."

cat > "/etc/nginx/sites-available/${SITE_KEY}" <<NGINX_CONF
server {
    listen 80;
    server_name ${DOMAIN};

    # ── ModSecurity WAF ────────────────────────────────────────────────
    modsecurity on;
    modsecurity_rules_file /etc/modsecurity/modsecurity.conf;

    root /var/www/${SITE_KEY};
    index index.html;

    access_log /var/log/nginx/${SITE_KEY}/access.log;
    error_log  /var/log/nginx/${SITE_KEY}/error.log;

    # ── 前端路由（SPA 单页应用） ──────────────────────────────────────────
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # ── API 反向代理 + 限流（隐藏后端真实 IP） ─────────────────────────
    location /api/ {
        limit_req zone=${SITE_KEY}_api_limit burst=50 nodelay;

        proxy_pass http://${BACKEND_IP}:8000;

        proxy_set_header Host                   \$host;
        proxy_set_header X-Real-IP              \$remote_addr;
        proxy_set_header X-Forwarded-For        \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto      \$scheme;
        proxy_set_header X-Site-Key             ${SITE_KEY};

        # 超时控制
        proxy_connect_timeout                   30s;
        proxy_read_timeout                      60s;
        proxy_send_timeout                      30s;

        # 缓冲控制
        proxy_buffering                         off;
        proxy_request_buffering                 off;
    }

    # ── 登录接口限流（5 次/分钟） ──────────────────────────────────────────
    location /api/admin/auth/login {
        limit_req zone=${SITE_KEY}_login_limit burst=3 nodelay;

        proxy_pass http://${BACKEND_IP}:8000;

        proxy_set_header Host                   \$host;
        proxy_set_header X-Real-IP              \$remote_addr;
        proxy_set_header X-Forwarded-For        \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto      \$scheme;
        proxy_set_header X-Site-Key             ${SITE_KEY};

        proxy_connect_timeout                   30s;
        proxy_read_timeout                      60s;
        proxy_send_timeout                      30s;
    }

    # ── WebSocket 代理（用于实时消息推送） ────────────────────────────────
    location /ws/ {
        proxy_pass http://${BACKEND_IP}:8000;
        proxy_http_version                      1.1;
        proxy_set_header Upgrade                \$http_upgrade;
        proxy_set_header Connection             "upgrade";
        proxy_set_header Host                   \$host;
        proxy_set_header X-Real-IP              \$remote_addr;
        proxy_set_header X-Forwarded-For        \$proxy_add_x_forwarded_for;
        proxy_set_header X-Site-Key             ${SITE_KEY};

        proxy_connect_timeout                   30s;
        proxy_read_timeout                      3600s;
        proxy_send_timeout                      30s;
    }

    # ── 静态资源缓存 ──────────────────────────────────────────────────────
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot|webp|avif)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # ── 安全响应头 ────────────────────────────────────────────────────────
    add_header X-Frame-Options           "SAMEORIGIN" always;
    add_header X-Content-Type-Options    "nosniff"    always;
    add_header X-XSS-Protection          "1; mode=block" always;
    add_header Referrer-Policy           "strict-origin-when-cross-origin" always;

    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # 禁止访问敏感路径
    location ~ (\.env|composer\.json|package\.json|yarn\.lock)$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}
NGINX_CONF

ln -sf "/etc/nginx/sites-available/${SITE_KEY}" "/etc/nginx/sites-enabled/${SITE_KEY}"
echo "  ✅ Nginx 配置: /etc/nginx/sites-available/${SITE_KEY}"
echo ""

# ─── 5. 创建限流配置 ────────────────────────────────────────────────────────
echo "[5/10] 创建 Nginx rate limiting 配置..."
cat > /etc/nginx/conf.d/rate-limit-${SITE_KEY}.conf <<RATE_LIMIT
# H5 站点 ${SITE_KEY} 限流配置
limit_req_zone \$binary_remote_addr zone=${SITE_KEY}_api_limit:10m rate=100r/s;
limit_req_zone \$binary_remote_addr zone=${SITE_KEY}_login_limit:10m rate=5r/m;
RATE_LIMIT
echo "  ✅ 限流配置: /etc/nginx/conf.d/rate-limit-${SITE_KEY}.conf"
echo ""

# ─── 6. 测试 Nginx 配置 ────────────────────────────────────────────────────
echo "[6/10] 测试 Nginx 配置..."
nginx -t
echo "  ✅ Nginx 配置测试通过"
echo ""

# ─── 7. 部署前端文件 ────────────────────────────────────────────────────────
echo "[7/10] 部署前端文件..."

# 支持通过环境变量 FRONTEND_URL 指定前端构建包下载地址
# 未设置时创建占位页面
if [ -n "${FRONTEND_URL:-}" ]; then
    echo "  从 ${FRONTEND_URL} 下载前端文件..."
    TMP_FILE=$(mktemp)
    if wget -q -O "$TMP_FILE" "$FRONTEND_URL"; then
        tar -xzf "$TMP_FILE" -C "/var/www/${SITE_KEY}"
        rm -f "$TMP_FILE"
        echo "  ✅ 前端文件部署完成"
    else
        rm -f "$TMP_FILE"
        echo "  ⚠️  下载失败，创建占位页面"
        cat > "/var/www/${SITE_KEY}/index.html" <<HTML_EOF
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${SITE_KEY} - 部署待完成</title>
  <style>
    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
    .card { background: white; padding: 2rem 3rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }
    h1 { color: #faad14; }
    p { color: #666; }
  </style>
</head>
<body>
  <div class="card">
    <h1>⏳ 站点部署中</h1>
    <p>站点 Key: <strong>${SITE_KEY}</strong></p>
    <p>请上传前端构建文件到 <code>/var/www/${SITE_KEY}</code></p>
  </div>
</body>
</html>
HTML_EOF
        echo "  ✅ 占位页面已创建"
    fi
else
    # 创建占位 index.html
    cat > "/var/www/${SITE_KEY}/index.html" <<HTML_EOF
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${SITE_KEY} - 部署待完成</title>
  <style>
    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
    .card { background: white; padding: 2rem 3rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }
    h1 { color: #faad14; }
    p { color: #666; }
  </style>
</head>
<body>
  <div class="card">
    <h1>⏳ 站点部署中</h1>
    <p>站点 Key: <strong>${SITE_KEY}</strong></p>
    <p>请上传前端构建文件到 <code>/var/www/${SITE_KEY}</code></p>
  </div>
</body>
</html>
HTML_EOF
    echo "  ✅ 占位页面已创建（未设置 FRONTEND_URL）"
    echo "  提示: 设置 FRONTEND_URL 环境变量可自动下载前端构建包"
fi
echo ""

# ─── 8. 申请 SSL 证书 ──────────────────────────────────────────────────────
echo "[8/10] 申请 Let's Encrypt SSL 证书..."
# 先检查是否已有证书
if certbot certificates 2>/dev/null | grep -q "Domain: ${DOMAIN}"; then
    echo "  ⚠️  域名 ${DOMAIN} 已有 SSL 证书，尝试续期..."
    certbot renew --non-interactive
else
    certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${EMAIL}" --redirect
fi
echo "  ✅ SSL 证书配置完成"
echo ""

# ─── 9. 重启 Nginx ────────────────────────────────────────────────────────
echo "[9/10] 重启 Nginx..."
systemctl restart nginx
echo "  ✅ Nginx 已重启"
echo ""

# ─── 10. 设置 SSL 自动续期 ────────────────────────────────────────────────────
echo "[10/10] 设置 SSL 自动续期（每天 3:00）..."
# 确保 certbot 续期命令已存在
if ! command -v certbot &>/dev/null; then
    echo "  ⚠️  certbot 未安装，跳过 SSL 续期配置"
else
    # 写入每日 SSL 续期 cron job
    CRON_JOB="0 3 * * * root certbot renew --quiet --post-hook 'systemctl reload nginx'"
    CRON_FILE="/etc/cron.d/certbot-renew-${SITE_KEY}"
    
    if [ -f "$CRON_FILE" ]; then
        echo "  ⚠️  SSL 续期 cron job 已存在，跳过"
    else
        echo "$CRON_JOB" > "$CRON_FILE"
        chmod 644 "$CRON_FILE"
        echo "  ✅ SSL 续期 cron job: $CRON_FILE"
    fi
fi
echo ""

# ─── 完成 ────────────────────────────────────────────────────────────────────
echo "=========================================="
echo "  ✅ 部署完成"
echo "=========================================="
echo "访问地址:       https://${DOMAIN}"
echo "站点目录:       /var/www/${SITE_KEY}"
echo "Nginx 配置:     /etc/nginx/sites-available/${SITE_KEY}"
echo "日志目录:       /var/log/nginx/${SITE_KEY}"
echo ""
echo "下一步:"
echo "  1. 上传前端构建文件到 /var/www/${SITE_KEY}"
echo "     (或设置 FRONTEND_URL 重新运行本脚本)"
echo "  2. 运行验证脚本: ./verify-h5-deployment.sh ${SITE_KEY} ${DOMAIN}"
echo "  3. SSL 已配置每日 3:00 自动续期"
echo "=========================================="
