#!/bin/bash
# scripts/remove-h5-site.sh
# H5 站点卸载脚本
# 用法: ./remove-h5-site.sh <site_key> <domain>
#
# 功能:
#   1. 删除 Let's Encrypt SSL 证书
#   2. 删除 Nginx 配置
#   3. 删除前端文件
#   4. 删除日志
#   5. 重启 Nginx

set -euo pipefail

SITE_KEY=$1
DOMAIN=$2

if [ -z "$SITE_KEY" ] || [ -z "$DOMAIN" ]; then
  echo "用法: $0 <site_key> <domain>"
  echo "示例: $0 wechat-01 h5-wechat.example.com"
  exit 1
fi

echo "=========================================="
echo "  卸载 H5 站点"
echo "=========================================="
echo "站点 Key:    ${SITE_KEY}"
echo "域名:        ${DOMAIN}"
echo "=========================================="
echo ""

# ── 确认卸载 ─────────────────────────────────────────────────────────────────
read -r -p "⚠️  确认卸载站点 ${SITE_KEY} (${DOMAIN})？(y/N) " CONFIRM
if [ "${CONFIRM:-}" != "y" ] && [ "${CONFIRM:-}" != "Y" ]; then
  echo "取消卸载。"
  exit 0
fi
echo ""

# ─── 1. 删除 SSL 证书 ───────────────────────────────────────────────────────
echo "[1/4] 删除 SSL 证书..."
if certbot certificates 2>/dev/null | grep -q "Domain: ${DOMAIN}"; then
    certbot delete --cert-name "${DOMAIN}" --non-interactive 2>/dev/null || true
    echo "  ✅ SSL 证书已删除"
else
    echo "  ⚠️  未找到 ${DOMAIN} 的 SSL 证书，跳过"
fi
echo ""

# ─── 2. 删除 Nginx 配置 ─────────────────────────────────────────────────────
echo "[2/4] 删除 Nginx 配置..."
if [ -f "/etc/nginx/sites-enabled/${SITE_KEY}" ]; then
    rm -f "/etc/nginx/sites-enabled/${SITE_KEY}"
    echo "  ✅ 已删除软链接: sites-enabled/${SITE_KEY}"
fi
if [ -f "/etc/nginx/sites-available/${SITE_KEY}" ]; then
    rm -f "/etc/nginx/sites-available/${SITE_KEY}"
    echo "  ✅ 已删除配置: sites-available/${SITE_KEY}"
fi
echo ""

# ─── 3. 删除前端文件 ────────────────────────────────────────────────────────
echo "[3/4] 删除前端文件..."
if [ -d "/var/www/${SITE_KEY}" ]; then
    rm -rf "/var/www/${SITE_KEY}"
    echo "  ✅ 已删除站点目录: /var/www/${SITE_KEY}"
else
    echo "  ⚠️  站点目录不存在，跳过"
fi
echo ""

# ─── 4. 删除日志 ────────────────────────────────────────────────────────────
echo "[4/4] 删除日志..."
if [ -d "/var/log/nginx/${SITE_KEY}" ]; then
    rm -rf "/var/log/nginx/${SITE_KEY}"
    echo "  ✅ 已删除日志目录: /var/log/nginx/${SITE_KEY}"
else
    echo "  ⚠️  日志目录不存在，跳过"
fi
echo ""

# ─── 重启 Nginx ─────────────────────────────────────────────────────────────
echo "重启 Nginx..."
if systemctl is-active --quiet nginx; then
    systemctl reload nginx || systemctl restart nginx
    echo "  ✅ Nginx 已重新加载"
else
    echo "  ⚠️  Nginx 未运行，跳过重启"
fi
echo ""

# ─── 完成 ────────────────────────────────────────────────────────────────────
echo "=========================================="
echo "  ✅ 卸载完成"
echo "=========================================="
echo "站点 ${SITE_KEY} (${DOMAIN}) 已从本服务器移除。"
echo ""
echo "注意:"
echo "  - 如果该域名还有其他站点使用同一 SSL 证书，certbot 可能保留证书"
echo "  - 如需彻底清除证书，请运行: certbot delete --cert-name ${DOMAIN}"
echo "  - 数据库中的站点记录需要单独删除"
echo "=========================================="
