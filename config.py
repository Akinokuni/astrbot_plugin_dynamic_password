from astrbot.core import AstrBotConfig

class PluginConfig:
    def __init__(self, config: AstrBotConfig):
        self._config = config

    def get_group_config(self, group_id: str) -> dict:
        """获取指定群组的配置"""
        groups = self._config.get("groups", {})
        return groups.get(str(group_id), {})

    def set_group_config(self, group_id: str, key: str, value: any):
        """设置指定群组的配置"""
        groups = self._config.get("groups", {})
        if str(group_id) not in groups:
            groups[str(group_id)] = {}
        
        groups[str(group_id)][key] = value
        self._config["groups"] = groups
        self._config.save_config()

    def is_enabled(self, group_id: str) -> bool:
        return self.get_group_config(group_id).get("enable", False)

    def get_secret(self, group_id: str) -> str:
        return self.get_group_config(group_id).get("secret", "default_secret")

    def get_length(self, group_id: str) -> int:
        return self.get_group_config(group_id).get("length", 6)
    
    def get_reject_on_fail(self, group_id: str) -> bool:
        return self.get_group_config(group_id).get("reject_on_fail", False)

    def get_reject_message(self, group_id: str) -> str:
        return self.get_group_config(group_id).get("reject_message", "动态密码错误")
