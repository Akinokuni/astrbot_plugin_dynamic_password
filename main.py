from datetime import datetime, timedelta
from typing import Any, Optional
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.api import logger
from .utils import generate_password, get_current_slot, get_beijing_time
from .config import PluginConfig

@register("astrbot_plugin_dynamic_password", "Aki_BG7ZGA", "动态入群密码插件", "0.1.1")
class DynamicPasswordPlugin(Star):
    def __init__(
        self,
        context: Context,
        config: Optional[AstrBotConfig] = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(context)
        cfg = (
            config
            or kwargs.get("config")
            or getattr(context, "config", None)
            or getattr(context, "_config", None)
        )
        if cfg is None:
            raise RuntimeError("AstrBot config is unavailable during plugin initialization.")
        self.config = PluginConfig(cfg)
        self.admins = [str(i) for i in cfg.get("admins_id", [])]

    @filter.command("加群密码")
    async def get_password(self, event: AiocqhttpMessageEvent, group_id: str = None):
        """获取加群密码。用法：/加群密码 [群号]"""
        if not group_id:
            if hasattr(event.message_obj, "group_id") and event.message_obj.group_id:
                group_id = str(event.message_obj.group_id)
            else:
                await event.send("请指定群号：/加群密码 <群号>")
                return

        if not self.config.is_enabled(group_id):
            await event.send(f"群 {group_id} 未开启动态密码验证。")
            return

        secret = self.config.get_secret(group_id)
        length = self.config.get_length(group_id)
        
        date_str, slot = get_current_slot()
        password = generate_password(secret, date_str, slot, length)
        
        slot_cn = "上午" if slot == "AM" else "下午"
        msg = f"群 {group_id} 当前({date_str} {slot_cn})入群密码：\n{password}\n\n请在入群申请理由中填写此密码。"
        await event.send(msg)

    @filter.command("动态密码配置")
    async def configure(self, event: AiocqhttpMessageEvent, group_id: str, action: str, value: str = None):
        """配置动态密码。用法：/动态密码配置 <群号> <enable/secret/length/reject/msg> [值]"""
        sender_id = str(event.get_sender_id())
        if sender_id not in self.admins:
            await event.send("无权操作。")
            return
            
        if action == "enable":
            enable = str(value).lower() == "true"
            self.config.set_group_config(group_id, "enable", enable)
            await event.send(f"群 {group_id} 动态密码已{'开启' if enable else '关闭'}。")
        elif action == "secret":
            if not value:
                await event.send("请提供 Secret 值。")
                return
            self.config.set_group_config(group_id, "secret", value)
            await event.send(f"群 {group_id} Secret 已更新。")
        elif action == "length":
            if not value or not value.isdigit():
                await event.send("请提供数字长度。")
                return
            self.config.set_group_config(group_id, "length", int(value))
            await event.send(f"群 {group_id} 密码长度已设置为 {value}。")
        elif action == "reject":
            reject = str(value).lower() == "true"
            self.config.set_group_config(group_id, "reject_on_fail", reject)
            await event.send(f"群 {group_id} 验证失败自动拒绝已{'开启' if reject else '关闭'}。")
        elif action == "msg":
            if not value:
                await event.send("请提供拒绝文案。")
                return
            self.config.set_group_config(group_id, "reject_message", value)
            await event.send(f"群 {group_id} 拒绝文案已更新。")
        else:
            await event.send("未知操作。支持：enable, secret, length, reject, msg")

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_request(self, event: AiocqhttpMessageEvent):
        """监听入群申请"""
        raw = getattr(event.message_obj, "raw_message", None)
        if not isinstance(raw, dict):
            return

        # 仅处理加群申请
        if raw.get("post_type") != "request" or raw.get("request_type") != "group" or raw.get("sub_type") != "add":
            return

        group_id = str(raw.get("group_id"))
        user_id = str(raw.get("user_id"))
        comment = raw.get("comment", "")
        flag = raw.get("flag")

        if not self.config.is_enabled(group_id):
            return

        secret = self.config.get_secret(group_id)
        length = self.config.get_length(group_id)
        
        # 获取当前时段密码
        date_str, slot = get_current_slot()
        current_pwd = generate_password(secret, date_str, slot, length)
        
        passwords_to_check = [current_pwd]
        
        # 容错机制：检查前15分钟是否还在上一时段的有效期内
        now = get_beijing_time()
        current_slot_start_hour = 0 if slot == "AM" else 12
        current_slot_start = now.replace(hour=current_slot_start_hour, minute=0, second=0, microsecond=0)
        
        if now - current_slot_start <= timedelta(minutes=15):
             prev_time = current_slot_start - timedelta(seconds=1)
             prev_date, prev_slot = get_current_slot(prev_time)
             prev_pwd = generate_password(secret, prev_date, prev_slot, length)
             passwords_to_check.append(prev_pwd)
             
        # 检查是否包含密码
        matched = False
        for pwd in passwords_to_check:
            if pwd in comment:
                matched = True
                break
        
        client = event.bot
        if matched:
            # 批准
            try:
                await client.set_group_add_request(
                    flag=flag,
                    sub_type="add",
                    approve=True,
                    reason="动态密码验证通过"
                )
                logger.info(f"群 {group_id} 用户 {user_id} 动态密码验证通过。")
            except Exception as e:
                logger.error(f"批准入群失败: {e}")
        else:
            # 拒绝（如果配置了 reject_on_fail）
            if self.config.get_reject_on_fail(group_id):
                reject_msg = self.config.get_reject_message(group_id)
                try:
                    await client.set_group_add_request(
                        flag=flag,
                        sub_type="add",
                        approve=False,
                        reason=reject_msg
                    )
                    logger.info(f"群 {group_id} 用户 {user_id} 动态密码验证失败，已拒绝。")
                except Exception as e:
                    logger.error(f"拒绝入群失败: {e}")
