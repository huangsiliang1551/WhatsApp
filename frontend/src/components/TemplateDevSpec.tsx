import { type JSX } from "react";
import { Button, Modal, Typography, message } from "antd";
import { CopyOutlined } from "@ant-design/icons";

const SPEC_TEXT = `H5 模板开发规范 v1.0

本规范用于开发 H5 会员端前端模板。请将此规范完整发送给 AI，AI 将一次性生成所有代码。

━━━━━━━━━━━━━━━━━━━━━━
一、硬性规定（必须严格遵守，不可修改）
━━━━━━━━━━━━━━━━━━━━━━

1. 包结构
   template-name.zip
   ├── index.html          ← 必须：入口文件
   ├── manifest.json       ← 必须：模板描述文件
   └── assets/             ← 必须：所有资源放在此目录
       ├── css/
       ├── js/
       ├── images/
       └── fonts/

2. manifest.json 格式（必须完全符合）
   {
     "name": "模板名称",
     "version": "1.0.0",
     "description": "模板描述",
     "author": "作者",
     "api_base": "/api",
     "site_key_param": "site_key",
     "required_apis": [
       "/api/h5/auth/login",
       "/api/h5/auth/register",
       "/api/h5/member/me",
       "/api/h5/wallet/balance",
       "/api/h5/wallet/transactions",
       "/api/h5/tasks/list",
       "/api/h5/tasks/{id}/start-product",
       "/api/h5/sign-in",
       "/api/h5/sign-in/status",
       "/api/h5/invite/my-link",
       "/api/h5/recharge/create",
       "/api/h5/withdraw/create",
       "/api/h5/messages/list",
       "/api/h5/tickets/list",
       "/api/h5/tickets/create",
       "/api/h5/sites/{site_key}/brand-config"
     ],
     "site_variables": {
       "brand_name": "品牌名称（字符串）",
       "logo_url": "Logo 图片 URL（字符串）",
       "favicon_url": "浏览器图标 URL（字符串）",
       "site_key": "站点唯一标识（字符串）",
       "default_language": "默认语言代码（字符串）",
       "template_id": "模板 ID（字符串）"
     },
     "pages": {
       "home": "首页（必须实现）",
       "login": "登录注册页（必须实现）",
       "tasks": "任务列表页",
       "task_detail": "任务详情页",
       "messages": "消息页",
       "profile": "个人中心",
       "recharge": "充值页",
       "withdraw": "提现页",
       "invite": "邀请好友",
       "orders": "订单页",
       "tickets": "工单页",
       "settings": "设置页"
     }
   }

3. site_key 传递方式
   - URL 查询参数: ?site_key=xxx
   - 所有页面必须从 URL 读取 site_key
   - 所有 API 调用必须携带 site_key

4. 品牌信息获取（必须在页面加载时调用）
   GET /api/h5/sites/{site_key}/brand-config
   返回: { brand_name, logo_url, favicon_url, site_key, default_language, template_id }
   - 用 brand_name 设置页面标题
   - 用 logo_url 设置 Logo 图片
   - 用 favicon_url 设置浏览器图标

5. 认证机制
   - 登录: POST /api/h5/auth/login { phone, password, site_key }
   - Token 存储: localStorage.setItem('h5_access_token', token)
   - 所有需认证的 API: Header 携带 Authorization: Bearer {token}
   - Token 过期: 返回 401 时跳转登录页

6. API 请求规范
   - 所有 API 以 /api 为前缀
   - GET 请求参数放 URL 查询字符串
   - POST 请求 body 为 JSON
   - 响应格式: { "items": [...], "total": N } 或 { "data": {...} }
   - 错误响应: { "detail": "错误信息" }

7. 路径规范
   - 所有资源路径使用相对路径（assets/css/style.css）
   - 禁止使用绝对路径（/css/style.css）
   - 禁止引用外部 CDN（所有资源必须包含在包内）
   - 禁止使用 eval()、document.write()、innerHTML 插入用户数据

━━━━━━━━━━━━━━━━━━━━━━
二、可自定义部分（上传者自由发挥）
━━━━━━━━━━━━━━━━━━━━━━

1. 视觉设计
   - 颜色方案（主色、辅助色、背景色等）
   - 字体选择（必须包含在包内）
   - 圆角、阴影、间距
   - 动画效果
   - 图标风格（线性/填充/自定义）

2. 页面布局
   - 底部导航样式（固定/浮动/圆角）
   - 顶栏样式（透明/纯色/渐变）
   - 卡片样式（阴影/边框/圆角）
   - 列表样式（卡片式/列表式/瀑布流）
   - 是否使用 SPA 路由（hash 路由或页面跳转）

3. 技术选型
   - 纯 HTML/CSS/JS（推荐，最轻量）
   - 或使用 Vue/React（需要打包）
   - 或使用任何 CSS 框架（Tailwind/Bootstrap 等）

4. 交互设计
   - 按钮样式和动画
   - 加载动画
   - 下拉刷新
   - 弹窗样式
   - Toast 提示样式

5. 页面内容（以下页面可选实现）
   - 订单页、工单页、邀请页、排行榜页
   - 如果未实现某个页面，访问时显示"功能暂未开放"

6. 首页布局
   - Banner 区域（可选）
   - 钱包余额展示方式
   - 签到入口样式
   - 任务卡片样式
   - 快捷操作入口

━━━━━━━━━━━━━━━━━━━━━━
三、核心 API 接口说明（AI 必须实现对接）
━━━━━━━━━━━━━━━━━━━━━━

1. 认证
   POST /api/h5/auth/login
   Body: { "phone": "13800138000", "password": "123456", "site_key": "xxx" }
   Response: { "access_token": "jwt...", "refresh_token": "jwt...", "user": {...} }

   POST /api/h5/auth/register
   Body: { "phone": "13800138000", "password": "123456", "site_key": "xxx" }
   Response: { "access_token": "jwt...", "user": {...} }

   GET /api/h5/member/me
   Headers: Authorization: Bearer {token}
   Response: { "id": "...", "phone": "...", "display_name": "...", ... }

2. 钱包
   GET /api/h5/wallet/balance?site_key=xxx
   Response: { "system_balance": "100.00", "task_balance": "50.00" }

   GET /api/h5/wallet/transactions?site_key=xxx&page=1&size=20
   Response: { "items": [{ "id", "type", "amount", "created_at" }], "total": N }

3. 任务
   GET /api/h5/tasks/list?site_key=xxx
   Response: { "items": [{ "id", "package_name", "status", "progress" }] }

   POST /api/h5/tasks/{id}/start-product
   Body: { "product_id": "xxx" }
   Response: { "status": "completed/failed", "message": "..." }

4. 签到
   POST /api/h5/sign-in?site_key=xxx
   Response: { "consecutive_days": 3, "reward": "1.00" }

   GET /api/h5/sign-in/status?site_key=xxx
   Response: { "signed_today": true, "consecutive_days": 3 }

5. 充值
   POST /api/h5/recharge/create
   Body: { "amount": 100, "channel_id": "xxx", "site_key": "xxx" }
   Response: { "order_id": "...", "pay_url": "..." }

6. 提现
   POST /api/h5/withdraw/create
   Body: { "amount": 50, "site_key": "xxx" }
   Response: { "id": "...", "status": "pending", "fee": "1.00" }

7. 消息
   GET /api/h5/messages/list?site_key=xxx&page=1&size=20
   Response: { "items": [{ "id", "title", "content", "is_read", "created_at" }] }

8. 工单
   POST /api/h5/tickets/create
   Body: { "subject": "问题标题", "content": "问题描述", "site_key": "xxx" }
   Response: { "id": "...", "status": "open" }
`;

interface TemplateDevSpecProps {
  open: boolean;
  onClose: () => void;
}

export function TemplateDevSpec({ open, onClose }: TemplateDevSpecProps): JSX.Element {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(SPEC_TEXT);
      message.success("规范已复制到剪贴板");
    } catch {
      message.error("复制失败，请手动选择复制");
    }
  };

  return (
    <Modal
      title="H5 模板开发规范"
      open={open}
      onCancel={onClose}
      width={900}
      footer={
        <Button type="primary" icon={<CopyOutlined />} onClick={handleCopy}>
          一键复制规范
        </Button>
      }
      styles={{ body: { maxHeight: "70vh", overflow: "auto" } }}
    >
      <Typography.Paragraph type="secondary">
        以下规范需完整提供给 AI 以生成 H5 模板包。顶部按钮可一键复制整段文本。
      </Typography.Paragraph>
      <pre style={{
        fontSize: 13, lineHeight: 1.7,
        background: "#f5f5f5", padding: 16, borderRadius: 6,
        whiteSpace: "pre-wrap", wordBreak: "break-word",
        fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace",
      }}>
        {SPEC_TEXT}
      </pre>
    </Modal>
  );
}
