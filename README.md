# AstrBot 插件 · B 站链接识别与直播通知

在 QQ 群聊或私聊里发送 B 站链接，机器人会回复封面、标题、作者和内容摘要。给 UP 主添加直播订阅后，机器人会把开播、下播通知发到指定群。插件运行在 AstrBot，QQ 由 NapCat 通过 OneBot v11 接入。

[快速安装](#快速安装) · [使用手册](docs/usage.md) · [直播通知](docs/live.md) · [从 NapCat 原版迁移](docs/migration.md) · [常见问题](docs/troubleshooting.md)

## 功能

| 场景 | 支持内容 |
| --- | --- |
| 识别分享 | BV／AV 号、b23 短链、QQ 小程序 JSON／XML 分享；支持视频、动态、番剧、专栏、直播间等内容 |
| 下载视频 | 普通视频和分 P；可按指令或在识别后自动下载，完成后发回原会话，也可从控制台保存到电脑 |
| 订阅直播 | 多主播、多群、按北京时间分时段检测；支持跨午夜、手动通知和按群补发 |
| 通知卡片 | 可展示直播封面、主播头像、直播间二维码和本场时长；支持自定义贴纸和手动发送素材 |
| 管理控制台 | 扫码登录 B 站、设置群范围、预览解析、管理下载任务、查看通知记录和导出脱敏诊断 |

![开播卡片示例，包含主播头像、直播标题和直播间二维码](docs/images/card-start-amis.jpg)

## 快速安装

1. 准备 **AstrBot 4.29.4 或更高的 4.x 版本**，启用 OneBot v11（`aiocqhttp`）适配器，让已登录 QQ 的 NapCat 反向连接 AstrBot。
2. 在 **AstrBot 所在的服务器或容器** 安装 **Node.js 20.3+**，确认 AstrBot 进程可执行 `node --version`。下载需要合并音视频时还要安装 FFmpeg。插件自带前端和 Node 业务模块，安装时无需运行 `npm install`。
3. 在 AstrBot 插件管理页通过仓库 URL 安装，或上传插件安装包 `astrbot_plugin_bili_recognizer-<版本>.zip`。手动安装时，将源码放入 `data/plugins/astrbot_plugin_bili_recognizer/`，确保目录下直接包含 `main.py` 和 `metadata.yaml`。
4. 打开插件详情中的 **dashboard**。只有一个 OneBot 实例时会自动选用；多个实例时，在 AstrBot 插件配置中填写负责本插件的 **平台实例 ID**，保存并重载。

已有 NapCat 原版订阅或登录凭据的用户，可在首次启用前按说明迁移。[数据迁移指南](docs/migration.md)

## 第一次使用

**识别链接**　在机器人可响应的群聊或私聊中，用另一个 QQ 账号发送真实的 B 站视频链接即可。若只想预览回复，可在控制台打开「链接测试」。

**下载视频**　发送以下任一指令，将尖括号及其中内容替换为实际链接或编号。`P2` 表示第二个分 P，省略时默认下载 P1。

```text
/bili下载 <视频链接或 BV 号> P2
/下载视频 <b23 短链>
```

**订阅直播**　在控制台的「直播订阅」中输入 UID 或直播间号，填写目标 QQ 群，勾选开播／下播通知，保存订阅并开启检测。首次检测只记录当前状态；如果主播已经开播，可点击手动发送。图片卡片需要配置可从 AstrBot 访问的文转图服务。[卡片配置与通知规则](docs/live.md)

## 仓库目录

| 路径 | 用途 |
| --- | --- |
| `main.py`、`engine.py` | AstrBot 插件入口、OneBot 消息收发和 Node 子进程通信 |
| `metadata.yaml`、`_conf_schema.json` | 插件信息、兼容版本和平台实例设置 |
| `lib/` | Node 运行入口、链接解析、直播检测、视频下载及控制台后端 |
| `views/dashboard/`、`assets/card/` | AstrBot 控制台页面和卡片素材 |
| `docs/` | 使用、迁移、排错与开发文档 |
| `test/`、`tools/` | 自动测试、诊断与开发工具 |

[开发与测试](docs/development.md) · [更新日志](CHANGELOG.md)

## 许可证

项目采用 ISC 许可证，随包的二维码库采用 MIT 许可证。[LICENSE](LICENSE) · [第三方来源与许可](THIRD_PARTY_NOTICES.md)
