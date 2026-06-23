#!/bin/bash
# scripts/verify-h5-deployment.sh
# H5 站点部署验证脚本
# 用法: ./verify-h5-deployment.sh <site_key> <domain>
#
# 检查项:
#   1. 域名可访问（200）
#   2. SSL 证书有效
#   3. API 反向代理工作
#   4. 后端 IP 隐藏（响应中不含 IP）
#   5. 前端文件存在

set -euo pipefail

SITE_KEY=$1
DOMAIN=$2

if [ -z "$SITE_KEY" ] || [ -z "$DOMAIN" ]; then
  echo "用法: $0 <site_key> <domain>"
  echo "示例: $0 wechat-01 h5-wechat.example.com"
  exit 1
fi

echo "=========================================="
echo "  H5 站点部署验证"
echo "=========================================="
echo "站点 Key:    ${SITE_KEY}"
echo "域名:        ${DOMAIN}"
echo "=========================================="
echo ""

PASS=0
FAIL=0
TOTAL=5

#───────────────────────────────────────────────────────────────────────────────
# 1. 检查域名可访问
#───────────────────────────────────────────────────────────────────────────────
echo -n "[1/${TOTAL}] 域名可访问: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}" --max-time 10 || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ PASS (HTTP ${HTTP_CODE})"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL (HTTP ${HTTP_CODE})"
  FAIL=$((FAIL + 1))
fi

#───────────────────────────────────────────────────────────────────────────────
# 2. 检查 SSL 证书有效
#───────────────────────────────────────────────────────────────────────────────
echo -n "[2/${TOTAL}] SSL 证书有效: "
SSL_RESULT=$(curl -s -o /dev/null -w "%{ssl_verify_result}" "https://${DOMAIN}" --max-time 10 2>&1 || echo "9")
if [ "$SSL_RESULT" = "0" ]; then
  echo "✅ PASS"
  PASS=$((PASS + 1))
else
  # 检查是否有证书（可能是自签名或过期）
  CERT_EXPIRY=$(echo | openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null || echo "unknown")
  echo "❌ FAIL (verify=${SSL_RESULT}, cert=${CERT_EXPIRY})"
  FAIL=$((FAIL + 1))
fi

#───────────────────────────────────────────────────────────────────────────────
# 3. 检查 API 代理工作
#───────────────────────────────────────────────────────────────────────────────
echo -n "[3/${TOTAL}] API 代理工作: "
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}/api/health" --max-time 10 || echo "000")
# 200 或 422（缺少必要参数）都表明 API 代理本身在工作
if [ "$API_CODE" = "200" ] || [ "$API_CODE" = "422" ]; then
  echo "✅ PASS (HTTP ${API_CODE})"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL (HTTP ${API_CODE})"
  FAIL=$((FAIL + 1))
fi

#───────────────────────────────────────────────────────────────────────────────
# 4. 检查后端 IP 隐藏
#───────────────────────────────────────────────────────────────────────────────
echo -n "[4/${TOTAL}] 后端 IP 隐藏: "
API_RESPONSE=$(curl -s "https://${DOMAIN}/api/health" --max-time 10 || echo "")
# 检查响应中是否包含明文 IP 地址
if echo "$API_RESPONSE" | grep -qE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'; then
  echo "❌ FAIL（响应中包含后端 IP 地址）"
  FAIL=$((FAIL + 1))
else
  echo "✅ PASS"
  PASS=$((PASS + 1))
fi

#───────────────────────────────────────────────────────────────────────────────
# 5. 检查前端文件存在
#───────────────────────────────────────────────────────────────────────────────
echo -n "[5/${TOTAL}] 前端文件存在: "
if [ -f "/var/www/${SITE_KEY}/index.html" ]; then
  FILE_SIZE=$(stat -c%s "/var/www/${SITE_KEY}/index.html" 2>/dev/null || echo "0")
  echo "✅ PASS (${FILE_SIZE} bytes)"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL (未找到 /var/www/${SITE_KEY}/index.html)"
  FAIL=$((FAIL + 1))
fi

#───────────────────────────────────────────────────────────────────────────────
# 结果汇总
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  验证结果"
echo "=========================================="
echo "通过: ${PASS} / ${TOTAL}"
echo "失败: ${FAIL} / ${TOTAL}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "  ✅ 部署验证全部通过！"
  exit 0
else
  echo "  ❌ 有 ${FAIL} 项验证失败，请检查。"
  echo ""
  echo "排查建议:"
  echo "  1. 确认 DNS 已解析到本机: dig ${DOMAIN}"
  echo "  2. 确认防火墙开放 80/443: ss -tlnp | grep -E ':(80|443) '"
  echo "  3. 检查 Nginx 状态: systemctl status nginx"
  echo "  4. 检查后端服务: systemctl status whatsapp-api"
  echo "  5. 查看 Nginx 错误日志: tail -50 /var/log/nginx/${SITE_KEY}/error.log"
  echo "  6. 重新运行部署: ./deploy-h5-site.sh ${SITE_KEY} ${DOMAIN} <backend_ip> <email>"
  exit 1
fi
