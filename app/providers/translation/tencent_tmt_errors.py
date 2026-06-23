"""Tencent Cloud Machine Translation (TMT) error code definitions.

Maps Tencent Cloud API error codes to user-friendly Chinese prompts.
Based on the official TMT error code documentation:
https://cloud.tencent.com/document/product/551/30637
https://cloud.tencent.com/document/product/551/15619
"""

# ── TMT Region definitions ─────────────────────────────────────────────

TMT_REGIONS: list[dict[str, str]] = [
    {"region": "ap-guangzhou",  "label": "广州 (ap-guangzhou)",         "endpoint": "tmt.ap-guangzhou.tencentcloudapi.com"},
    {"region": "ap-beijing",    "label": "北京 (ap-beijing)",           "endpoint": "tmt.ap-beijing.tencentcloudapi.com"},
    {"region": "ap-shanghai",   "label": "上海 (ap-shanghai)",          "endpoint": "tmt.ap-shanghai.tencentcloudapi.com"},
    {"region": "ap-nanjing",    "label": "南京 (ap-nanjing)",           "endpoint": "tmt.ap-nanjing.tencentcloudapi.com"},
    {"region": "ap-chengdu",    "label": "成都 (ap-chengdu)",           "endpoint": "tmt.ap-chengdu.tencentcloudapi.com"},
    {"region": "ap-hongkong",   "label": "香港 (ap-hongkong)",          "endpoint": "tmt.ap-hongkong.tencentcloudapi.com"},
    {"region": "ap-singapore",  "label": "新加坡 (ap-singapore)",       "endpoint": "tmt.ap-singapore.tencentcloudapi.com"},
    {"region": "ap-tokyo",      "label": "东京 (ap-tokyo)",             "endpoint": "tmt.ap-tokyo.tencentcloudapi.com"},
    {"region": "na-siliconvalley", "label": "硅谷 (na-siliconvalley)",  "endpoint": "tmt.na-siliconvalley.tencentcloudapi.com"},
]

# ── Error code → Chinese prompt mapping ────────────────────────────────

# Common error codes (通用于所有腾讯云 API)
TMT_ERROR_CODE_PROMPTS: dict[str, str] = {
    "ActionOffline": "该 API 接口已下线，请联系技术支持。",
    "AuthFailure.InvalidAuthorization": "请求头部的 Authorization 不符合腾讯云标准，请检查签名计算过程。",
    "AuthFailure.InvalidSecretId": "密钥非法，SecretId 不是云 API 密钥类型，请在控制台检查密钥是否正确。",
    "AuthFailure.MFAFailure": "多因子认证（MFA）错误，请检查 MFA 配置。",
    "AuthFailure.SecretIdNotFound": "密钥不存在，请在【访问管理】控制台检查密钥是否已被删除或禁用。",
    "AuthFailure.SignatureExpire": "签名已过期，本地时间与服务器时间相差超过 5 分钟，请同步系统时间。",
    "AuthFailure.SignatureFailure": "签名验证失败，请对照签名方法文档检查签名计算过程。",
    "AuthFailure.TokenFailure": "临时 Token 错误，请检查 Token 是否有效。",
    "AuthFailure.UnauthorizedOperation": "请求未授权，请检查 CAM 权限配置。",
    "DryRunOperation": "DryRun 操作验证通过。",
    "FailedOperation": "操作失败，请稍后重试。",
    "InternalError": "腾讯云内部错误，请稍后重试。",
    "InvalidAction": "请求的接口不存在，请检查 Action 参数。",
    "InvalidParameter": "请求参数错误，请检查参数格式和类型。",
    "InvalidParameterValue": "请求参数取值错误，请检查参数值是否在有效范围内。",
    "InvalidRequest": "请求 body 的 multipart 格式错误。",
    "IpInBlacklist": "您的 IP 地址已被加入黑名单。",
    "IpNotInWhitelist": "您的 IP 地址不在白名单中。",
    "LimitExceeded": "请求超过配额限制，请稍后重试。",
    "MissingParameter": "缺少必填参数，请检查请求参数是否完整。",
    "NoSuchProduct": "请求的产品不存在。",
    "NoSuchVersion": "请求的接口版本不存在。",
    "RequestLimitExceeded": "请求频率超过限制，请降低调用频率。",
    "RequestLimitExceeded.GlobalRegionUinLimitExceeded": "主账号请求频率超过限制。",
    "RequestLimitExceeded.IPLimitExceeded": "当前 IP 请求频率超过限制。",
    "RequestLimitExceeded.UinLimitExceeded": "主账号请求频率超过限制。",
    "RequestSizeLimitExceeded": "请求包超过大小限制。",
    "ResourceInUse": "资源被占用，请稍后重试。",
    "ResourceInsufficient": "资源不足。",
    "ResourceNotFound": "请求的资源不存在。",
    "ResourceUnavailable": "资源不可用。",
    "ResponseSizeLimitExceeded": "返回包超过大小限制。",
    "ServiceUnavailable": "服务暂时不可用，请稍后重试。",
    "UnauthorizedOperation": "未授权操作，请检查您的权限配置。",
    "UnknownParameter": "存在未定义的请求参数，请检查参数列表。",
    "UnsupportedOperation": "不支持的操作。",
    "UnsupportedProtocol": "请求协议错误，仅支持 GET 和 POST。",
    "UnsupportedRegion": "接口不支持所传地域（Region），请选择其他地域。",
}

# TMT business-specific error codes
TMT_BIZ_ERROR_CODE_PROMPTS: dict[str, str] = {
    "FailedOperation.InsertErr": "数据插入失败，请稍后重试。",
    "FailedOperation.NoFreeAmount": "本月免费额度已用完，如需继续使用请在机器翻译控制台升级为付费服务。",
    "FailedOperation.RequestAiLabErr": "内部请求错误，请稍后重试。",
    "FailedOperation.ServiceIsolate": "账号因欠费已停止服务，请在腾讯云账户充值后恢复。",
    "FailedOperation.UserNotRegistered": "机器翻译服务未开通，请在腾讯云控制台开通机器翻译服务。",
    "InternalError.BackendTimeout": "后台服务超时，请稍后重试。",
    "InternalError.ErrorUnknown": "未知错误，请联系技术支持。",
    "InternalError.RequestFailed": "请求失败，请稍后重试。",
    "InvalidParameter.DuplicatedSessionIdAndSeq": "重复的 SessionUuid 和 Seq 组合。",
    "InvalidParameter.MissingParameter": "参数错误，请检查必填参数是否完整。",
    "InvalidParameter.SeqIntervalTooLarge": "Seq 之间的间隙请不要大于 2000。",
    "LimitExceeded.LimitedAccessFrequency": "超出请求频率限制，请降低调用频率。",
    "UnauthorizedOperation.ActionNotFound": "请填写正确的 Action 字段名称。",
    "UnsupportedOperation.AudioDurationExceed": "音频分片长度超过限制，请保证分片长度小于 8 秒。",
    "UnsupportedOperation.TextTooLong": "单次请求 text 超过长度限制（2000 字符），请缩短文本。",
    "UnsupportedOperation.UnSupportedTargetLanguage": "不支持的目标语言，请参照语言列表选择正确的目标语言。",
    "UnsupportedOperation.UnsupportedLanguage": "不支持的语言，请参照语言列表。",
    "UnsupportedOperation.UnsupportedSourceLanguage": "不支持的源语言，请参照语言列表选择正确的源语言。",
}


def get_tmt_error_prompt(error_code: str) -> str | None:
    """Get the user-friendly Chinese prompt for a given TMT error code.

    Checks business error codes first, then common error codes.
    Returns None if no mapping is found.
    """
    if error_code in TMT_BIZ_ERROR_CODE_PROMPTS:
        return TMT_BIZ_ERROR_CODE_PROMPTS[error_code]
    if error_code in TMT_ERROR_CODE_PROMPTS:
        return TMT_ERROR_CODE_PROMPTS[error_code]
    return None


def get_tmt_error_prompt_with_code(error_code: str) -> str:
    """Get the user-friendly prompt, falling back to the raw error code if unmapped."""
    prompt = get_tmt_error_prompt(error_code)
    if prompt:
        return f"[{error_code}] {prompt}"
    return f"[{error_code}] 未知错误，请联系技术支持。"
