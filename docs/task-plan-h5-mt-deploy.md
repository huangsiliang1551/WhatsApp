# H5 多租户系统 — 一键部署脚本（H5MT-DEPLOY）

> **执行角色**: deploy_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 生成 Nginx + Let's Encrypt 一键部署脚本，实现自动化部署

---

## 一、部署架构

```
用户 → CDN（可选） → Nginx（H5 服务器）
                        ↓
                   反向代理 /api/*
                        ↓
                   后端 API（内网，隐藏真实 IP）
```

**安全要求**:
- 前端不能探测后端真实 IP（通过 Nginx 反向代理隐藏）
- 攻击一个 H5 站点不影响其他 H5（独立 Nginx server block）

---

## 二、一键部署脚本

### 2.1 主部署脚本

```bash
#!/bin/bash
# scripts/deploy-h5-site.sh
# H5 站点一键部署脚本
# 用法: ./deploy-h5-site.sh <site_key> <domain> <backend_ip> <email>

set -e

SITE_KEY=$1
DOMAIN=$2
BACKEND_IP=$3
EMAIL=$4

if [ -z "$SITE_KEY" ] || [ -z "$DOMAIN" ] || [ -z "$BACKEND_IP" ] || [ -z "$EMAIL" ]; then
  echo "用法: $0 <site_key> <domain> <backend_ip> <email>"
  echo "示例: $0 wechat-01 h5-wechat.example.com 192.168.1.100 admin@example.com"
  exit 1
fi

echo "=== H5 站点部署 ==="
echo "站点 Key: $SITE_KEY"
echo "域名: $DOMAIN"
echo "后端 IP: $BACKEND_IP"
echo "SSL 邮箱: $EMAIL"
echo ""

# 1. 安装依赖
echo "[1/7] 安装依赖..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx curl

# 2. 创建站点目录
echo "[2/7] 创建站点目录..."
mkdir -p /var/www/$SITE_KEY
mkdir -p /var/log/nginx/$SITE_KEY

# 3. 配置 Nginx
echo "[3/7] 配置 Nginx..."
cat > /etc/nginx/sites-available/$SITE_KEY << NGINX
server {
    listen 80;
    server_name $DOMAIN;

    root /var/www/$SITE_KEY;
    index index.html;

    access_log /var/log/nginx/$SITE_KEY/access.log;
    error_log /var/log/nginx/$SITE_KEY/error.log;

    # 前端路由（SPA）
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API 反向代理（隐藏后端真实 IP）
    location /api/ {
        proxy_pass http://$BACKEND_IP:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Site-Key $SITE_KEY;
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
        proxy_send_timeout 30s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINX

ln -sf /etc/nginx/sites-available/$SITE_KEY /etc/nginx/sites-enabled/

# 4. 测试 Nginx 配置
echo "[4/7] 测试 Nginx 配置..."
nginx -t

# 5. 部署前端文件
echo "[5/7] 部署前端文件..."
# TODO: 从构建服务器拉取前端文件
# 方案 A: wget 下载
# wget -O /tmp/h5-$SITE_KEY.tar.gz http://build-server/h5-$SITE_KEY.tar.gz
# tar -xzf /tmp/h5-$SITE_KEY.tar.gz -C /var/www/$SITE_KEY

# 方案 B: scp 上传
# scp user@build-server:/path/to/h5-$SITE_KEY.tar.gz /tmp/
# tar -xzf /tmp/h5-$SITE_KEY.tar.gz -C /var/www/$SITE_KEY

# 临时：创建占位 index.html
cat > /var/www/$SITE_KEY/index.html << HTML
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$SITE_KEY - 部署中</title>
</head>
<body>
  <h1>站点部署中...</h1>
  <p>站点 Key: $SITE_KEY</p>
  <p>请稍候，前端文件正在部署。</p>
</body>
</html>
HTML

# 6. 申请 SSL 证书
echo "[6/7] 申请 SSL 证书..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

# 7. 重启 Nginx
echo "[7/7] 重启 Nginx..."
systemctl restart nginx

echo ""
echo "=== 部署完成 ==="
echo "访问地址: https://$DOMAIN"
echo "站点目录: /var/www/$SITE_KEY"
echo "Nginx 配置: /etc/nginx/sites-available/$SITE_KEY"
echo "日志目录: /var/log/nginx/$SITE_KEY"
echo ""
echo "下一步: 上传前端文件到 /var/www/$SITE_KEY"
```

### 2.2 部署验证脚本

```bash
#!/bin/bash
# scripts/verify-h5-deployment.sh
# H5 站点部署验证脚本
# 用法: ./verify-h5-deployment.sh <domain>

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
  echo "用法: $0 <domain>"
  echo "示例: $0 h5-wechat.example.com"
  exit 1
fi

echo "=== H5 站点部署验证: $DOMAIN ==="
echo ""

PASS=0
FAIL=0

# 1. 检查域名可访问
echo -n "[1/5] 域名可访问: "
if curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN" | grep -q "200"; then
  echo "✅ PASS"
  ((PASS++))
else
  echo "❌ FAIL"
  ((FAIL++))
fi

# 2. 检查 SSL 证书
echo -n "[2/5] SSL 证书有效: "
if curl -s -o /dev/null -w "%{ssl_verify_result}" "https://$DOMAIN" | grep -q "0"; then
  echo "✅ PASS"
  ((PASS++))
else
  echo "❌ FAIL"
  ((FAIL++))
fi

# 3. 检查 API 代理
echo -n "[3/5] API 代理工作: "
if curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/api/health" | grep -q "200"; then
  echo "✅ PASS"
  ((PASS++))
else
  echo "❌ FAIL"
  ((FAIL++))
fi

# 4. 检查后端 IP 隐藏
echo -n "[4/5] 后端 IP 隐藏: "
RESPONSE=$(curl -s "https://$DOMAIN/api/health")
if echo "$RESPONSE" | grep -qv "[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}"; then
  echo "✅ PASS"
  ((PASS++))
else
  echo "❌ FAIL（响应中包含 IP 地址）"
  ((FAIL++))
fi

# 5. 检查前端文件
echo -n "[5/5] 前端文件存在: "
if [ -f "/var/www/$DOMAIN/index.html" ]; then
  echo "✅ PASS"
  ((PASS++))
else
  echo "❌ FAIL"
  ((FAIL++))
fi

echo ""
echo "=== 验证结果 ==="
echo "通过: $PASS / 5"
echo "失败: $FAIL / 5"

if [ $FAIL -eq 0 ]; then
  echo ""
  echo "✅ 部署验证全部通过！"
  exit 0
else
  echo ""
  echo "❌ 有 $FAIL 项验证失败，请检查。"
  exit 1
fi
```

### 2.3 站点卸载脚本

```bash
#!/bin/bash
# scripts/remove-h5-site.sh
# H5 站点卸载脚本
# 用法: ./remove-h5-site.sh <site_key> <domain>

SITE_KEY=$1
DOMAIN=$2

if [ -z "$SITE_KEY" ] || [ -z "$DOMAIN" ]; then
  echo "用法: $0 <site_key> <domain>"
  exit 1
fi

echo "=== 卸载 H5 站点: $SITE_KEY ($DOMAIN) ==="
echo ""
read -p "确认卸载？(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "取消卸载。"
  exit 0
fi

# 1. 删除 SSL 证书
echo "[1/4] 删除 SSL 证书..."
certbot delete --cert-name $DOMAIN --non-interactive

# 2. 删除 Nginx 配置
echo "[2/4] 删除 Nginx 配置..."
rm -f /etc/nginx/sites-enabled/$SITE_KEY
rm -f /etc/nginx/sites-available/$SITE_KEY

# 3. 删除前端文件
echo "[3/4] 删除前端文件..."
rm -rf /var/www/$SITE_KEY

# 4. 删除日志
echo "[4/4] 删除日志..."
rm -rf /var/log/nginx/$SITE_KEY

# 重启 Nginx
systemctl restart nginx

echo ""
echo "=== 卸载完成 ==="
```

---

## 三、使用流程

### 3.1 创建新站点

**后台操作**:
```
POST /api/platform/sites
Body: {
  "site_key": "wechat-01",
  "brand_name": "微信渠道",
  "domain": "h5-wechat.example.com"
}
```

**生成部署脚本**:
```
POST /api/platform/sites/wechat-01/deploy-script
Body: {
  "backend_ip": "192.168.1.100",
  "email": "admin@example.com"
}
```

**服务器执行**:
```bash
# 将生成的脚本保存到服务器
cat > deploy.sh << 'SCRIPT'
<生成的脚本内容>
SCRIPT

chmod +x deploy.sh
./deploy.sh
```

**验证部署**:
```
POST /api/platform/sites/wechat-01/verify-deployment
```

---

## 四、任务清单

| 任务 | 文件 | 行数 |
|------|------|------|
| 主部署脚本 | scripts/deploy-h5-site.sh | ~150 行 |
| 部署验证脚本 | scripts/verify-h5-deployment.sh | ~80 行 |
| 站点卸载脚本 | scripts/remove-h5-site.sh | ~50 行 |
| **总计** | | ~230 行 |

---

## 发给部署 Agent 的文本

```
你是部署 Agent（H5 一键部署轮）。请读取 docs/task-plan-h5-mt-deploy.md，一次性实现全部部署脚本，不要中途暂停。

核心任务：

1. 主部署脚本（scripts/deploy-h5-site.sh ~150行）：
   - 安装 Nginx + Certbot
   - 配置 Nginx server block（反向代理 /api/* 隐藏后端 IP）
   - 部署前端文件
   - 申请 Let's Encrypt SSL 证书
   - 重启 Nginx

2. 部署验证脚本（scripts/verify-h5-deployment.sh ~80行）：
   - 检查域名可访问
   - 检查 SSL 证书有效
   - 检查 API 代理工作
   - 检查后端 IP 隐藏
   - 检查前端文件存在

3. 站点卸载脚本（scripts/remove-h5-site.sh ~50行）：
   - 删除 SSL 证书
   - 删除 Nginx 配置
   - 删除前端文件
   - 删除日志

约束：脚本可在 Ubuntu/Debian 服务器执行，一次性完成。开始吧。
```
