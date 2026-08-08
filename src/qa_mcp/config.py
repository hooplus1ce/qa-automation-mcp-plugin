import os

from dotenv import load_dotenv

# 启动时加载项目根目录 .env (若存在)。已存在的进程环境变量优先于 .env,
# 因此 .mcp.json / 系统环境中的显式配置不会被覆盖。
def _env_project_dir() -> str:
    """读取客户端注入的用户项目根 (CLAUDE_PROJECT_DIR, 可能带引号)。"""
    return os.getenv("CLAUDE_PROJECT_DIR", "").strip().strip('"').strip("'")


# 启动时加载 .env: 优先用户项目 .env (CLAUDE_PROJECT_DIR, 插件化部署时
# 用户的配置应覆盖插件自带默认), 其次进程 cwd 的 .env (插件目录/本地项目);
# 已存在的进程环境变量始终优先, 不会被 .env 覆盖。
_proj_env = _env_project_dir()
if _proj_env:
    load_dotenv(os.path.join(_proj_env, ".env"))
load_dotenv()


def _resolve_project_dir() -> str:
    """定位用户项目根目录。

    插件化部署时 MCP 服务进程由 `uv run --directory ${CLAUDE_PLUGIN_ROOT}`
    拉起, 进程 cwd 是插件安装目录而非用户项目; Claude Code 会向子进程注入
    CLAUDE_PROJECT_DIR 环境变量, 用它还原用户项目根, 使相对路径 (粘贴图片/
    截图/下载/导出目录) 始终落在用户自己的项目里。未注入时回退进程 cwd
    (本地直跑 / 无项目概念的客户端)。
    """
    proj = _env_project_dir()
    if proj and os.path.isdir(proj):
        return os.path.abspath(proj)
    return os.getcwd()


PROJECT_DIR = _resolve_project_dir()


def project_path(path: str) -> str:
    """将相对路径锚定到用户项目根目录 (绝对路径/空串原样返回)。"""
    if not path or os.path.isabs(path):
        return path
    return os.path.join(PROJECT_DIR, os.path.expanduser(path))


CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")
# 鼠标光标可视化 + 目标高亮 服务级默认开关 (visualize=None 时生效, 默认关闭)
VISUAL_EFFECTS = os.getenv("VISUAL_EFFECTS", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# 以下相对目录统一锚定用户项目根: 插件化部署时进程 cwd 是插件目录,
# 若保持相对路径会把证据/导出/下载写进插件安装目录, 用户侧无法访问。
EVIDENCE_DIR = project_path("evidence_assets")
OUTPUT_DIR = project_path("output_testcases")
# download_file 工具默认下载保存目录 (相对用户项目根, 可环境变量覆盖)
DOWNLOAD_DIR = project_path(os.getenv("DOWNLOAD_DIR", "downloads"))


# ==================== 时序/等待参数 (统一调优成功率) ====================
# 全部可用环境变量覆盖; 慢环境/慢页面整体放大时改一处即可, 无需逐文件改魔法数字。
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


# 元素定位等待超时 (click/fill/select_option/press 的 wait_for visible)。
# 默认 10s: 慢页面留足缓冲, 且单次定位失败成本可控 (配合重试仍整体有界)。
ELEMENT_WAIT_TIMEOUT_MS = _env_int("ELEMENT_WAIT_TIMEOUT_MS", 10000)
# 全局执行看门狗: 任何工具调用超过该上限即强制中断并释放串行队列。
# 必要性: Chrome 假死/CDP 连接半开时 Playwright 协议调用可能无限等待,
# 动作级 timeout 不会触发 (等待的是协议响应); 该上限远小于客户端 30min 超时。
TOOL_MAX_EXECUTION_MS = _env_int("TOOL_MAX_EXECUTION_MS", 300000)
# 动作链单步执行上限: 单个 click/fill/select/press 超过即记为失败,
# 防止链中一个死动作把整条链及后续所有工具调用堵死。
ACTION_STEP_TIMEOUT_MS = _env_int("ACTION_STEP_TIMEOUT_MS", 90000)
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
