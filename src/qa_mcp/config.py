import os

from dotenv import load_dotenv

# 启动时加载项目根目录 .env (若存在)。已存在的进程环境变量优先于 .env,
# 因此 .mcp.json / 系统环境中的显式配置不会被覆盖。
load_dotenv()

CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")
# 鼠标光标可视化 + 目标高亮 服务级默认开关 (visualize=None 时生效, 默认关闭)
VISUAL_EFFECTS = os.getenv("VISUAL_EFFECTS", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
EVIDENCE_DIR = "evidence_assets"
OUTPUT_DIR = "output_testcases"


# ==================== 时序/等待参数 (统一调优成功率) ====================
# 全部可用环境变量覆盖; 慢环境/慢页面整体放大时改一处即可, 无需逐文件改魔法数字。
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


# 元素定位等待超时 (click/fill/select_option/press 的 wait_for visible)
ELEMENT_WAIT_TIMEOUT_MS = _env_int("ELEMENT_WAIT_TIMEOUT_MS", 6000)
# 点击/输入后的统一观察轮询窗口 (动态层/消息捕获)
OBSERVE_WAIT_MS = _env_int("OBSERVE_WAIT_MS", 1500)
# Ant Design 下拉: 首次等待新下拉挂载; 后续每轮重试等待; 重试总轮数; 重试间隔
SELECT_WAIT_FIRST_MS = _env_int("SELECT_WAIT_FIRST_MS", 5000)
SELECT_WAIT_RETRY_MS = _env_int("SELECT_WAIT_RETRY_MS", 1000)
SELECT_RETRY_ATTEMPTS = _env_int("SELECT_RETRY_ATTEMPTS", 6)
SELECT_POLL_INTERVAL_MS = _env_int("SELECT_POLL_INTERVAL_MS", 200)
# 统一"定位-执行"重试 (SPA 重渲染/元素 detach/短暂遮挡): 尝试次数与间隔
ACTION_RETRY_ATTEMPTS = _env_int("ACTION_RETRY_ATTEMPTS", 3)
ACTION_RETRY_BACKOFF_MS = _env_int("ACTION_RETRY_BACKOFF_MS", 500)
# CDP 首次连接失败退避重试: 次数与初始间隔 (指数退避 x2)
CONNECT_RETRY_ATTEMPTS = _env_int("CONNECT_RETRY_ATTEMPTS", 3)
CONNECT_RETRY_BACKOFF_MS = _env_int("CONNECT_RETRY_BACKOFF_MS", 1500)
