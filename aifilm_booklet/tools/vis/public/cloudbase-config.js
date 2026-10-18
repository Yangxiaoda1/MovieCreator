// 用户打开的是 CloudBase 静态托管页面，不是下面这个 API 地址。
// apiUrl 只供前端自动保存/读取审查意见；本地预览 fallback 时可留空。
// 公网示例：
// https://<env-id>-<uin>.<region>.app.tcloudbase.com/storyboard-api
window.STORYBOARD_CONFIG = {
  docId: "storyboard-review-demo",
  apiUrl: "",
  assetVersion: "dev"
};
