"""Bilingual captions for application updates."""
TEXT = {
    "enabled": ("启用自动更新", "Enable automatic updates"),
    "help": ("后台检查并下载正式版；只有确认“立即更新”后才会退出安装。配置和音频保留。", "Check and download stable releases in the background. Installation starts only after you confirm Update now. Your settings and audio are retained."),
    "check": ("立即检查更新", "Check for updates"),
    "ready": ("自动下载，确认后安装。", "Download automatically; install after confirmation."),
    "checking": ("正在检查更新…", "Checking for updates…"),
    "downloading": ("正在下载 v{version}：{percent}%", "Downloading v{version}: {percent}%"),
    "available": ("v{version} 已就绪，点击“立即检查更新”查看。", "v{version} is ready. Select Check for updates to view it."),
    "current": ("当前 v{version} 已是最新正式版。", "v{version} is the latest stable release."),
    "failed": ("更新未完成：{error}", "Update could not be completed: {error}"),
    "title": ("软件更新", "Application update"),
    "new": ("发现新版本 v{version}", "New version v{version} is available"),
    "install": ("立即更新", "Update now"),
    "later": ("稍后", "Later"),
    "open": ("打开下载页面", "Open download page"),
    "source": ("源码运行不会自动替换文件，请从发布页面下载或更新源码。", "Source checkouts are never replaced automatically. Download a release or update your checkout."),
    "confirm": ("将保存当前修改并退出软件，安装 v{version} 后重新启动。配置、台词、音频和陪伴包会保留。是否继续？", "Save changes and exit to install v{version}, then restart. Settings, dialogues, audio and companion packs will be retained. Continue?"),
    "busy": ("正在生成语音或操作本地接口，请等待任务完成后再更新。", "Speech generation or a local API operation is running. Wait for it to finish before updating."),
    "instances": ("此目录还有其他声伴实例正在运行，请自行保存并退出后重试。", "Another instance from this directory is running. Save and exit it before retrying."),
    "cancelled": ("后台更新已取消；仍可手动检查。", "Background update cancelled. You can still check manually."),
    "success": ("已成功更新至 v{version}，原配置和资源继续使用。", "Updated to v{version}. Your existing settings and resources are retained."),
    "previous_failed": ("上次更新未完成，旧数据保留。请重新检查更新；详情：{error}", "The previous update was not completed. Existing data was retained. Check again to retry. Details: {error}"),
    "retry": ("下载失败可重新检查；GitHub 无法连接时可稍后重试。", "Check again to retry a failed download. If GitHub is unreachable, try later."),
    "verified": ("文件大小和 SHA256 校验通过，等待你确认安装。", "Package size and SHA256 verified. Waiting for your confirmation."),
}


def ut(key, **values):
    from .i18n import tr
    return tr("updates." + key, TEXT[key][0], **values)
