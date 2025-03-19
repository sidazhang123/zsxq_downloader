# zsxq_downloader
download topics, comments, and any included pictures or downloadable urls from zhishixingqiu, by topic's created time span

根据登录账号cookie中的ACCESS_TOKEN、星球编号、主题创建的时间范围，下载星球中的主题、评论及所包含的图片及文件下载链接，最终合成pdf（太多则会分文件）

配置见脚本前几行

需安装pdfkit包，其它都是builtin

因网络、pdf生成错误中断程序可重新运行.py从错误点恢复：
* 下载主题 -> 更新temp/crawl_status.json -> ... ->出错：读取status:继续 -> 下载完毕 -> 将全部下载内容生成temp/*.html并存入temp/htmls.pkl -> 从.pkl读取并生成pdf
* 因在temp/htmls.pkl存在时运行脚本会直接根据它生成pdf，有时需要手动删除.pkl来触发恢复下载

