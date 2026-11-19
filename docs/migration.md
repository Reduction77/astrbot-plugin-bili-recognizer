# 从 NapCat 原版迁移

[返回 README](../README.md)

首次启用前停用旧插件，备份其配置和数据目录。将旧配置文件复制为 AstrBot 插件数据目录下的 `config.json`，将旧数据目录中的 `bili-session.json`、`live-subscriptions.json`、`downloads/`、`live-cards/` 复制到同一目录。默认目标目录是 `data/plugin_data/astrbot_plugin_bili_recognizer/`。自定义贴纸复制到新插件的 `assets/card/custom/`。沿用原数据格式，整套数据只需复制一次。若已在新版创建订阅，请先备份新版数据，整文件覆盖会替换已有记录。

重载后核对账号、目标群、检测状态和下载记录。跨机器迁移时请更新 FFmpeg 和渲染服务地址。
