"""浏览器自动化工具 Provider 扩展 (FastMCP 3.x/4.0 规范)。"""

from collections.abc import Sequence

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from qa_mcp.tools.action_chain import execute_action_chain_impl
from qa_mcp.tools.browser import (
    analyze_elements_impl,
    capture_screenshot_impl,
    click_interact_impl,
    fill_input_impl,
    probe_dynamic_layers_impl,
    switch_target_page_impl,
    wait_for_condition_impl,
)
from qa_mcp.tools.recorder import execute_and_record_impl, start_recording_impl
from qa_mcp.tools.vision import mimo_describe_image_impl

class BrowserAutomationProvider(Provider):
    """浏览器自动化工具集: 页面分析 / 点击 / 输入 / 截图 / 用例录制 / 条件等待。"""

    def __init__(self) -> None:
        super().__init__()
        self._tools: list[Tool] = [
            Tool.from_function(
                analyze_elements_impl,
                name="analyze_current_page",
                description="分析当前 Chrome 页面。递归提取包括主文档和嵌套 iframe 内的所有可见交互元素并生成定位器。",
            ),
            Tool.from_function(
                start_recording_impl,
                name="start_recording",
                description="初始化一个新的自动化测试用例录制会话。",
            ),
            Tool.from_function(
                execute_and_record_impl,
                name="execute_and_record",
                description="利用 UI 组件适配器智能执行输入/点击等动作，并实时将最优高韧性语义定位步骤记录到用例中。",
            ),
            Tool.from_function(
                probe_dynamic_layers_impl,
                name="probe_dynamic_layers",
                description="探查当前页面或指定 iframe 中交互后出现的可见弹窗、消息气泡、下拉/日期/级联悬浮层，并返回内部文本、属性、HTML 和可交互元素。detail=brief(默认, 剪枝输出)|full(完整 html/文本)。",
            ),
            Tool.from_function(
                click_interact_impl,
                name="click_interact",
                description="统一点击工具：by=css/xpath 传 selector（支持 iframe_selector 链式穿透），by=role 传 role+name（get_by_role 语义定位，适合 Portal 弹层），by=coordinate 传 x/y（coordinate_space=top 为顶层视口坐标，可点 VTable 内部）。click_type=single/double；detail=brief/full 控制观察输出体积。visualize 三态（None=跟随配置，默认关）。返回 visual_effects + observation（dynamic_layers/new_layers 浮层弹窗消息 + summary 摘要 + focus 域隔离 + navigation 的 URL/iframe 跳转对比）。",
            ),
            Tool.from_function(
                fill_input_impl,
                name="fill_input",
                description="文本框输入工具：by=css/xpath + selector（支持 iframe_selector 穿透）；value 为空=清空。input_method=type（逐字键盘，触发键盘事件）/fill（原生填充）；clear_first 默认清空；press_enter 可回车；detail=brief/full。visualize 三态（None=跟随配置，默认关）。返回 visual_effects + observation（浮层/消息 + summary + focus + 跳转）。",
            ),
            Tool.from_function(
                capture_screenshot_impl,
                name="capture_screenshot",
                description="截取当前页面截图：用 CDP 采集（不会卡在字体加载上），保存到 evidence_assets/ 并返回内联 PNG 图片（支持图片的客户端可直接查看）。filename 可指定输出文件名（默认时间戳，自动补 .png）；full_page=True 截整页（含滚动区外内容），False(默认) 只截当前视口。返回文本摘要（文件路径/尺寸/字节数）+ 图片内容。用于视觉证据、页面状态留档、UI 断言前的实况确认。",
            ),
            Tool.from_function(
                mimo_describe_image_impl,
                name="mimo_describe_image",
                description="仅当当前主模型为纯文本模型（如 DeepSeek-R1、DeepSeek-V3、GLM 纯文本版等）无法识别图片时使用的降级视觉识别工具。将本地图片路径、公网 URL 或对话框粘贴的图片发送给小米 MiMo-V2.5 模型解析并返回文本描述。若当前主模型本身具备原生多模态视觉能力（如 GPT-4o、Claude 3.5/3.7 Sonnet、Claude Opus 5、Gemini、Qwen2.5-VL、GLM-4V 等），绝对禁止调用本工具，必须由主模型直接看图。",
            ),
            Tool.from_function(
                switch_target_page_impl,
                name="switch_target_page",
                description="显式切换/重绑 MCP 操作目标标签页（按 URL 子串匹配）并锁定。默认机制：首次调用自动锁定一个标签页，后续操作固定作用于该页，不受新开/切换标签页影响；测试页被误关或需操作另一系统页面时用本工具重绑。返回新目标页 URL/标题。",
            ),
            Tool.from_function(
                execute_action_chain_impl,
                name="execute_action_chain",
                description="批量动作链：一次调用顺序执行 click/fill/select_option/press 多个动作，最后统一观察一次并返回 observation（浮层/消息/跳转）。actions 每项 {action, by, selector, iframe_selector, value, click_type, input_method, clear_first, press_enter, key, description}；stop_on_error=True 遇错即停（默认），False 收集 failed 继续。用于减少 Agent 往返。降级容错：每项可选 fallbacks: [{完整动作参数}] 配置备用定位，主定位失败时按序尝试；执行器还会自动附加兜底变体（antd 常驻 dropdown 的 li[title=...] 选项自动补/去 >> nth=N 变体、role↔css 互退），全部失败才中断，错误信息含已尝试的定位方案数。生成脚本时为易歧义动作（下拉选项点击、弹层按钮）配置 fallbacks 可显著提高整链成功率。",
            ),
            Tool.from_function(
                wait_for_condition_impl,
                name="wait_for_condition",
                description="等待页面条件成立（轮询），超时返回最后一次状态快照、不抛错。condition：element_visible(selector 可见,默认)/element_hidden(selector 不可见或不存在)/element_has_text(selector 可见文本包含 expected_text,exact=True 精确相等)/text_present(目标 iframe 或全部 frame 页面文本出现 expected_text)/url_contains(URL 包含 expected_text)。典型用法：提交表单后 wait_for_condition(condition='text_present', expected_text='新增成功', timeout_ms=10000) 等成功消息出现，再断言收尾。",
            ),
        ]

    async def _list_tools(self) -> Sequence[Tool]:
        return self._tools
