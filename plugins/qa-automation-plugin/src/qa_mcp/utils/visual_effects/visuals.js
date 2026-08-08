(() => {
  const KEY = '__drissionpageMcpVisuals';
  const HOST_ID = '__drissionpage_mcp_visuals__';
  const CURSOR_SIZE = 32;
  const CURSOR_HOTSPOT_X = 5;
  const CURSOR_HOTSPOT_Y = 10;
  const MOVEMENT_SLOWDOWN = 2;
  const EASING = 'cubic-bezier(0.16, 1, 0.3, 1)';
  // Transparent 32 px frame and hotspot from the active Windows 11 Dark HD pointer.cur.
  const CURSOR_IMAGE = 'data:image/png;base64,'
    + 'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAACEUlEQVR4nO2WzasSURiHH79u3+W9N6JPMoqg'
    + 'oF3LyDFcC+GyjeIfonVX7dxE0MbtDWoR/gGCq9pJgtgsA1voYkBFmTlNE2c4E4OMedWZ2viDl/la/J73vOc978BOO+30'
    + 'nxVb45sTBUA8yLjX6x222+3LQEpFEkisAA5Htm3XHaXpdPoGuAicB05FDiGEeC6N6/W6G1KGYbwHrgCXgNORQti2/VK'
    + 'aqno7tVrNhRiNRh+A60A6Ugh7AcAPMRwOP0YOYQcA/FMIIcSrIIAVEMnQIMRfAJZA7ANnQoMQKwD8ELPZrFepVB6ECi'
    + 'FOACCjVCr9gSiXyw+Bg1AgxAkB/BDj8fgLcGNhY0YPgK8czWbzBXBVnZipdVYhvjEtYBiGe7UsK+GbF/F1AJLrGGqaR'
    + 'jabda+ZTMYN0zR/FIvFz6FMS7GkBJqmOa1Wy5tRzmQy+TYYDD51Op3XhULhMXBbzQtZgr2NN6IIAKhWq66pZVmTbrf'
    + '7Lp/PPwFk+91TxteAQ+DC1hPTVkdxOp12zRuNhmuu6/pxLpd7CsiWuwvcVBnvK+OzKvPtjub5fP5MGsrl9pa83++/BR'
    + '4B94FbvtF8TmWc2mTzLVPcNM0jIcRXIcR3XdePVMZ31FIfKGMv2626SCoW8JxQBnu+nrblFpEdB/xUz6H8I8YC3sUV'
    + 'hBdSv5Spre5D+0GNLXnv1dP7vtiaOxGWfgOOKpPMpe76TQAAAABJRU5ErkJggg==';
  if (globalThis[KEY]?.version === 9) {
    globalThis[KEY].mount();
    return;
  }
  // 旧版本脚本可能已驻留在打开的页面中 (幂等版本检查命中时会跳过替换, 旧行为继续生效,
  // 曾导致"成功分支已改为立即消失但仍停留 2.4s")。版本升级后这里整体重建:
  // 先清理旧实例的定时器/动画, mount() 会移除旧 host 再挂载新 host。
  if (globalThis[KEY]) {
    try { globalThis[KEY].disable(); } catch (_) {}
  }

  const state = {
    host: null,
    root: null,
    cursor: null,
    highlight: null,
    label: null,
    animation: null,
    monitorFrame: 0,
    hideTimer: 0,
    x: Math.max(24, Math.round(innerWidth * 0.35)),
    y: Math.max(24, Math.round(innerHeight * 0.35)),
    sequence: 0,
    enabled: false,
    last: null,
    lastMotion: null,
  };

  function cursorTransform(x, y) {
    return `translate3d(${x - CURSOR_HOTSPOT_X}px, ${y - CURSOR_HOTSPOT_Y}px, 0)`;
  }

  function setCursor(x, y) {
    state.x = Number.isFinite(x) ? x : state.x;
    state.y = Number.isFinite(y) ? y : state.y;
    if (state.cursor) state.cursor.style.transform = cursorTransform(state.x, state.y);
  }

  function mount() {
    if (state.host?.isConnected) return true;
    const documentRoot = document.documentElement || document.body;
    if (!documentRoot) {
      setTimeout(mount, 25);
      return false;
    }

    document.getElementById(HOST_ID)?.remove();
    const host = document.createElement('div');
    host.id = HOST_ID;
    host.style.cssText = [
      'position:fixed', 'inset:0', 'width:100vw', 'height:100vh',
      'pointer-events:none', 'z-index:2147483647', 'overflow:visible',
      'contain:layout style paint'
    ].join(';');
    const root = host.attachShadow({mode: 'open'});
    const style = document.createElement('style');
    style.textContent = `
      :host { all: initial; }
      .cursor {
        position: fixed; left: 0; top: 0; width: 32px; height: 32px;
        display: block; object-fit: contain; opacity: 0; pointer-events: none;
        image-rendering: auto; will-change: transform, opacity;
        transition: opacity 100ms cubic-bezier(.16, 1, .3, 1);
      }
      .highlight {
        position: fixed; left: 0; top: 0; min-width: 2px; min-height: 2px;
        --accent: #22d3ee;
        color: var(--accent); border: 2px solid currentColor; border-radius: 6px; opacity: 0;
        box-shadow: 0 0 0 2px rgb(34 211 238 / 20%), 0 0 18px rgb(34 211 238 / 55%);
        pointer-events: none; overflow: visible; will-change: transform, opacity;
        transition: opacity 100ms cubic-bezier(.16, 1, .3, 1), color 140ms ease-out;
      }
      .highlight::before {
        content: ''; position: absolute; inset: -5px; border: 1px solid currentColor;
        border-radius: 9px; opacity: .48; will-change: transform, opacity;
        animation: target-breathe 900ms ease-in-out infinite alternate;
      }
      .highlight[data-state='success'] {
        --accent: #34d399;
        box-shadow: 0 0 0 2px rgb(52 211 153 / 20%), 0 0 18px rgb(52 211 153 / 55%);
      }
      .highlight[data-state='error'] {
        --accent: #fb7185;
        box-shadow: 0 0 0 2px rgb(251 113 133 / 20%), 0 0 18px rgb(251 113 133 / 60%);
      }
      .highlight[data-state='error']::before { animation: target-error 160ms linear 3; }
      .label {
        position: absolute; left: -2px; bottom: calc(100% + 7px); max-width: 320px;
        padding: 4px 7px; border: 1px solid #22d3ee; border-radius: 4px;
        background: #07111f; color: #e6fdff; box-shadow: 0 0 10px rgb(34 211 238 / 35%);
        font: 600 11px/1.25 ui-monospace, SFMono-Regular, Consolas, monospace;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .ripple {
        position: fixed; width: 16px; height: 16px; margin: -8px 0 0 -8px;
        border: 2px solid #22d3ee; border-radius: 50%; pointer-events: none;
        box-shadow: 0 0 12px #22d3ee; animation: click-ripple 560ms ease-out forwards;
      }
      @keyframes target-breathe {
        from { transform: scale3d(.985, .985, 1); opacity: .3; }
        to { transform: scale3d(1.025, 1.025, 1); opacity: .68; }
      }
      @keyframes target-error {
        0%, 100% { transform: translate3d(0, 0, 0); }
        50% { transform: translate3d(5px, 0, 0); }
      }
      @keyframes click-ripple {
        from { transform: scale(.35); opacity: 1; }
        to { transform: scale(4.2); opacity: 0; }
      }
      @media (prefers-reduced-motion: reduce) {
        .cursor, .highlight { transition-duration: .01ms !important; }
        .highlight::before, .ripple {
          animation-duration: .01ms !important; animation-iteration-count: 1 !important;
        }
      }
    `;
    const highlight = document.createElement('div');
    highlight.className = 'highlight';
    highlight.dataset.state = 'targeting';
    const label = document.createElement('div');
    label.className = 'label';
    highlight.appendChild(label);
    const cursor = document.createElement('img');
    cursor.className = 'cursor';
    cursor.src = CURSOR_IMAGE;
    cursor.alt = '';
    cursor.draggable = false;
    root.append(style, highlight, cursor);
    documentRoot.appendChild(host);

    state.host = host;
    state.root = root;
    state.cursor = cursor;
    state.highlight = highlight;
    state.label = label;
    setCursor(state.x, state.y);
    return true;
  }

  function stopMotion() {
    if (state.monitorFrame) cancelAnimationFrame(state.monitorFrame);
    state.monitorFrame = 0;
    if (state.animation) state.animation.cancel();
    state.animation = null;
  }

  async function moveTo(x, y, minDuration, maxDuration) {
    mount();
    stopMotion();
    const startX = state.x;
    const startY = state.y;
    const distance = Math.hypot(x - startX, y - startY);
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const lower = Math.max(0, Number(minDuration) || 0);
    const upper = Math.max(lower, Number(maxDuration) || lower);
    const duration = reducedMotion
      ? 0
      : Math.round(Math.min(
          upper,
          Math.max(lower, (110 + Math.sqrt(distance) * 7) * MOVEMENT_SLOWDOWN)
        ));
    const started = performance.now();
    let firstFrame = 0;
    let lastFrame = 0;
    let frameCount = 0;
    state.lastMotion = {
      driver: 'web_animations_api',
      animated_properties: ['transform'],
      easing: EASING,
      reduced_motion: reducedMotion,
      distance_px: Math.round(distance * 10) / 10,
      requested_duration_ms: duration,
      elapsed_ms: 0,
      sampled_frame_count: 0,
      average_frame_interval_ms: 0,
      estimated_fps: 0,
    };

    if (!duration || distance < 0.5) {
      setCursor(x, y);
      state.lastMotion.sampled_frame_count = 1;
      return snapshot();
    }

    let monitoring = true;
    const monitor = now => {
      if (!monitoring) return;
      if (!firstFrame) firstFrame = now;
      lastFrame = now;
      frameCount += 1;
      state.monitorFrame = requestAnimationFrame(monitor);
    };
    state.monitorFrame = requestAnimationFrame(monitor);
    const animation = state.cursor.animate(
      [
        {transform: cursorTransform(startX, startY)},
        {transform: cursorTransform(x, y)},
      ],
      {duration, easing: EASING, fill: 'forwards'}
    );
    state.animation = animation;
    let completed = true;
    try {
      await animation.finished;
    } catch (_) {
      completed = false;
    }
    monitoring = false;
    if (state.monitorFrame) cancelAnimationFrame(state.monitorFrame);
    state.monitorFrame = 0;
    if (completed && state.animation === animation) setCursor(x, y);
    animation.cancel();
    if (state.animation === animation) state.animation = null;

    const elapsed = performance.now() - started;
    const intervals = Math.max(1, frameCount - 1);
    const average = frameCount > 1 ? (lastFrame - firstFrame) / intervals : 0;
    state.lastMotion.elapsed_ms = Math.round(elapsed * 10) / 10;
    state.lastMotion.sampled_frame_count = frameCount;
    state.lastMotion.average_frame_interval_ms = Math.round(average * 100) / 100;
    state.lastMotion.estimated_fps = average > 0 ? Math.round(10000 / average) / 10 : 0;
    return snapshot();
  }

  function show(payload) {
    mount();
    state.enabled = true;
    const sequence = ++state.sequence;
    if (state.hideTimer) clearTimeout(state.hideTimer);
    state.hideTimer = 0;
    const [left, top, width, height] = payload.rect;
    state.highlight.style.transform = `translate3d(${left}px, ${top}px, 0)`;
    state.highlight.style.width = `${Math.max(2, width)}px`;
    state.highlight.style.height = `${Math.max(2, height)}px`;
    state.highlight.style.opacity = '1';
    state.highlight.dataset.state = 'targeting';
    state.label.textContent = `${String(payload.action || 'ACTION').toUpperCase()}  ${payload.label || ''}`.trim();
    state.cursor.style.opacity = '1';
    state.last = {...payload, state: 'targeting'};
    return moveTo(
      payload.point[0],
      payload.point[1],
      payload.minDurationMs,
      payload.maxDurationMs
    ).then(result => {
      if (state.enabled && sequence === state.sequence && payload.action === 'click') {
        pulse(payload.point[0], payload.point[1]);
      }
      return result;
    });
  }

  function pulse(x, y) {
    if (!state.enabled || !mount()) return false;
    const ripple = document.createElement('div');
    ripple.className = 'ripple';
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    state.root.appendChild(ripple);
    setTimeout(() => ripple.remove(), 620);
    return true;
  }

  function finish(success) {
    if (!state.enabled || !state.cursor || !state.highlight) return false;
    const sequence = state.sequence;
    if (success) {
      // 成功: 视觉层与实际交互完成【同步】立即消失 —— 光标/高亮/波纹即刻清理
      // (100ms 淡出过渡由 CSS transition 提供), 不再停留 2.4s。
      state.highlight.dataset.state = 'success';
      if (state.last) state.last.state = 'success';
      if (state.hideTimer) clearTimeout(state.hideTimer);
      state.hideTimer = 0;
      state.cursor.style.opacity = '0';
      state.highlight.style.opacity = '0';
      state.root?.querySelectorAll('.ripple').forEach(node => node.remove());
      return true;
    }
    // 失败: 保留红框错误反馈, 短暂停留后淡出 (用户需要看到"未点中")
    const resultState = 'error';
    state.highlight.dataset.state = resultState;
    if (state.last) state.last.state = resultState;
    if (state.hideTimer) clearTimeout(state.hideTimer);
    state.hideTimer = setTimeout(() => {
      if (sequence !== state.sequence) return;
      state.cursor.style.opacity = '0';
      state.highlight.style.opacity = '0';
    }, 2600);
    return true;
  }

  function disable() {
    state.enabled = false;
    state.sequence += 1;
    if (state.hideTimer) clearTimeout(state.hideTimer);
    state.hideTimer = 0;
    stopMotion();
    if (state.cursor) state.cursor.style.opacity = '0';
    if (state.highlight) state.highlight.style.opacity = '0';
    state.root?.querySelectorAll('.ripple').forEach(node => node.remove());
    return true;
  }

  function snapshot() {
    return {
      mounted: Boolean(state.host?.isConnected),
      enabled: state.enabled,
      mode: 'cursor_highlight',
      cursor: {
        x: Math.round(state.x),
        y: Math.round(state.y),
        visible: state.cursor?.style.opacity === '1',
        style: 'windows_11_dark_hd',
        size: CURSOR_SIZE,
        hotspot: [CURSOR_HOTSPOT_X, CURSOR_HOTSPOT_Y],
        asset_loaded: Boolean(state.cursor?.complete && state.cursor.naturalWidth === CURSOR_SIZE),
      },
      highlight: state.last ? {
        visible: state.highlight?.style.opacity === '1',
        rect: state.last.rect,
        label: state.last.label,
        action: state.last.action,
        state: state.last.state,
      } : null,
      effects: {trail: false, highlight: true, label: true, click_feedback: true},
      rendering: state.lastMotion ? {...state.lastMotion} : null,
    };
  }

  globalThis[KEY] = {version: 9, mount, show, moveTo, pulse, finish, disable, snapshot};
  mount();
})();