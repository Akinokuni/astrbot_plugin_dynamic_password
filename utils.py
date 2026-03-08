import hashlib
from datetime import datetime, timedelta, timezone

def get_beijing_time() -> datetime:
    """获取北京时间"""
    return datetime.now(timezone(timedelta(hours=8)))

def get_current_slot(dt: datetime = None) -> tuple[str, str]:
    """获取当前时间槽：(日期YYYYMMDD, AM/PM)"""
    if dt is None:
        dt = get_beijing_time()
    
    date_str = dt.strftime("%Y%m%d")
    slot = "AM" if dt.hour < 12 else "PM"
    return date_str, slot

def generate_password(secret: str, date_str: str, slot: str, length: int = 6) -> str:
    """生成动态密码"""
    raw_str = f"{date_str}-{slot}-{secret}"
    hash_obj = hashlib.sha256(raw_str.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()
    
    # 提取纯数字
    digits = "".join(filter(str.isdigit, hash_hex))
    
    # 如果数字不够长，循环使用
    if len(digits) < length:
        digits = (digits * (length // len(digits) + 1))
        
    return digits[:length]

def check_password(input_pwd: str, secret: str, length: int = 6) -> bool:
    """验证密码，包含容错机制"""
    now = get_beijing_time()
    date_str, slot = get_current_slot(now)
    current_pwd = generate_password(secret, date_str, slot, length)
    
    if input_pwd == current_pwd:
        return True
        
    # 容错机制：检查前15分钟是否还在上一时段的有效期内
    # AM开始于00:00，PM开始于12:00
    current_slot_start_hour = 0 if slot == "AM" else 12
    current_slot_start = now.replace(hour=current_slot_start_hour, minute=0, second=0, microsecond=0)
    
    time_diff = now - current_slot_start
    
    if time_diff <= timedelta(minutes=15):
        # 计算上一时段
        prev_time = current_slot_start - timedelta(seconds=1)
        prev_date_str, prev_slot = get_current_slot(prev_time)
        prev_pwd = generate_password(secret, prev_date_str, prev_slot, length)
        if input_pwd == prev_pwd:
            return True
            
    return False
