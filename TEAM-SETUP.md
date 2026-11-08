# 建模手记 · 开发与部署

面向 Narutomaki-0721/AMC.github.io。Node 22.13+ 或 24，Python 3.11+。公开文章在 Git，私有任务与执行记录在 D1。

## 本地验证

```sh
npm ci
npm test
python -m unittest discover -s tests -p "test_*.py"
npm run build
npm run dev
```

开发服务器在终端输出本地地址。没有团队 API 时可直接阅读全部知识栏目。将 VITE_API_URL 设置成 Worker 地址后重新运行前端。本地调试可将 SITE_ORIGIN 指向 VitePress 终端输出的 origin。后端可用 Wrangler 的本地 D1 与独立的测试密钥运行。

## 部署团队 API

1. 在 Cloudflare 账户创建 D1 数据库。复制 worker/wrangler.example.jsonc 为同目录的 wrangler.jsonc，填数据库 ID、模型地址和模型标识。使用支持 JSON 输出的 Chat Completions 兼容模型。SITE_ORIGIN 是 Pages 的域名，SITE_BASE 是项目路径。
2. 在 worker 目录通过 Wrangler 执行 `wrangler d1 execute mcm-hub --remote --file schema.sql`。本地调试用 --local。
3. 使用 `wrangler secret put NAME` 分别设置 MODEL_KEY、DISPATCH_TOKEN、RUNNER_KEY、MEMBERS_JSON。DISPATCH_TOKEN 用只限目标仓库、具有 Actions 写权限的细粒度 GitHub token。RUNNER_KEY 是由管理员随机生成的长密钥，仅供执行器回报。
4. 每个成员用独立随机访问码。运行 `node scripts/member-code.mjs` 生成 256 位随机访问码和 SHA-256。将访问码私下交给该成员，MEMBERS_JSON 设置为形如 `{"成员访问码的sha256":{"name":"队长","approver":true}}` 的对象。移除对应哈希即撤销权限。成员输入的访问码仅保存在当前标签页的 sessionStorage。
5. 运行 `wrangler deploy`，记下返回的 HTTPS 地址。开发调试可用 `wrangler dev` 及不提交的 .dev.vars。不要将 .dev.vars 放进 Git。

## GitHub 设置

- Pages 的 Source 选 GitHub Actions。仓库变量 API_URL 填 Worker 地址，MODEL_URL 和 MODEL_NAME 与 Worker 配置一致。
- Actions secrets：RUNNER_KEY 与 Worker 相同；SEARCH_KEY 是 Brave Search API key；MODEL_KEY 只在执行收录时使用。
- 主分支合并后，Knowledge Pages 工作流构建和发布。手动运行同一工作流可以刷新公开站点。Pages 工作流需要仓库允许 Pages 部署；收录工作流需要能提交内容到 main。如果分支规则强制一切修改走 PR，则需要调整执行器为 PR 发布流程。
- 此版本的知识库文章公开。获发访问码的成员可对话、查看团队任务。审批成员可批准、拒绝、重做。输入的原始对话仅用于当前标签页，任务请求会存入 D1，模型调用本身仍经所配置的模型服务。
- 收录器读取允许域的 HTML 原文，跳过重定向和无法解析的 PDF。官方赛程和赛题限定 COMAP 域。需扩展来源时修改 scripts/collect.py 的 ALLOWED。按任务编号生成固定输出路径，重复执行同一任务会复用已有页面。不同任务可引用同一来源。

## 验收路径

1. 打开官方赛程文章，点击「问 AI」，请求收录一份资料。
2. 确认请求出现在「待审批」，普通成员无法执行审批。
3. 审批人同意后查看阶段。失败保留日志；重做新增一次执行。
4. 成功任务包含发布地址和提交号。「不同意」任务保留请求与审批时间。
5. 若访问码、Worker 地址或云服务仍未配置，先用上述本地测试核对状态流，再接入真实服务。
