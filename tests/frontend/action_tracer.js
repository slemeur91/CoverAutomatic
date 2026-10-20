// Records what each data-action of the panel does, to compare the event
// routing before and after a refactor (see test_actions.py).
//
// Every method of the panel class is wrapped: for one triggered action we
// keep the methods called directly by the event dispatchers, and the names
// of the panel properties whose value changed. Both are taken synchronously,
// right after the event, so the result does not depend on timing.
(() => {
  const DISPATCHERS = new Set([
    "_handleClick", "_handleActionClick", "_handleChange", "_handleInput", "_handleDragStart", "_handleHouseDragStart",
  ]);
  // Actions started by another event than a click
  const ACTION_EVENTS = { "rule-drag": ["dragstart"], "house-drag-start": ["pointerdown"] };
  const stack = [];
  let calls = null;

  window.__installTracer = () => {
    if (window.__tracerInstalled) return;
    window.__tracerInstalled = true;
    const Panel = customElements.get("cover-automatic-panel");
    for (let proto = Panel.prototype; proto && proto !== HTMLElement.prototype; proto = Object.getPrototypeOf(proto)) {
      for (const name of Object.getOwnPropertyNames(proto)) {
        if (name === "constructor") continue;
        const desc = Object.getOwnPropertyDescriptor(proto, name);
        if (!desc || typeof desc.value !== "function") continue;
        const original = desc.value;
        proto[name] = function (...args) {
          if (calls && stack.length && DISPATCHERS.has(stack[stack.length - 1]) && !DISPATCHERS.has(name)) {
            calls.add(name);
          }
          stack.push(name);
          try {
            return original.apply(this, args);
          } finally {
            stack.pop();
          }
        };
      }
    }
  };

  const snapshot = (el) => {
    const out = {};
    for (const key of Object.keys(el)) {
      if (!key.startsWith("_")) continue;
      let value;
      try {
        value = JSON.stringify(el[key], (k, v) => (v instanceof Node ? "[node]" : v));
      } catch (err) {
        value = "[unserializable]";
      }
      out[key] = value;
    }
    return out;
  };

  // First element of an action the user can operate: interactive and enabled
  // (the first "move up" button is disabled; some data-action attributes only
  // mark containers read by the code, like the day list of a condition).
  const INTERACTIVE = new Set(["BUTTON", "A", "INPUT", "SELECT", "TEXTAREA", "SUMMARY", "TR"]);
  const usable = (el) => !el.disabled && (INTERACTIVE.has(el.tagName) || el.hasAttribute("tabindex")
    || el.getAttribute("role") === "button" || el.dataset.action in ACTION_EVENTS);
  const firstEnabled = (action) => {
    const all = [...window.__el.shadowRoot.querySelectorAll(`[data-action="${CSS.escape(action)}"]`)];
    return all.find(usable) || null;
  };

  // Every data-action shown, with the events to send it.
  window.__listActions = () => {
    const seen = new Map();
    for (const node of window.__el.shadowRoot.querySelectorAll("[data-action]")) {
      const action = node.dataset.action;
      if (seen.has(action)) continue;
      const el = firstEnabled(action);
      if (!el) continue;
      if (ACTION_EVENTS[action]) { seen.set(action, ACTION_EVENTS[action]); continue; }
      const tag = el.tagName;
      const type = (el.getAttribute("type") || "").toLowerCase();
      const clickable = !["SELECT", "INPUT", "TEXTAREA"].includes(tag) || ["checkbox", "radio", "button", "file"].includes(type);
      seen.set(action, clickable ? ["click"] : ["input", "change"]);
    }
    return [...seen.entries()].map(([action, events]) => ({ action, events }));
  };

  window.__traceAction = (action, eventName) => {
    const panel = window.__el;
    const el = firstEnabled(action);
    if (!el) return null;
    const before = snapshot(panel);
    const domBefore = panel.shadowRoot.innerHTML;
    const emitted = [];
    const origDispatch = panel.dispatchEvent;
    panel.dispatchEvent = function (event) { emitted.push(event.type); return origDispatch.call(this, event); };
    calls = new Set();
    try {
      if (eventName === "dragstart") {
        el.dispatchEvent(new DragEvent("dragstart", { bubbles: true, composed: true, dataTransfer: new DataTransfer() }));
      } else if (eventName === "pointerdown") {
        const r = el.getBoundingClientRect();
        el.dispatchEvent(new PointerEvent("pointerdown", {
          bubbles: true, composed: true, button: 0, isPrimary: true, clientX: r.x + r.width / 2, clientY: r.y + 2,
        }));
      } else if (eventName === "click") {
        if (el.getAttribute("type") === "file") {
          // A file input opens the OS dialog on click: send its change instead
          el.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
          el.click();
        }
      } else {
        el.dispatchEvent(new Event(eventName, { bubbles: true }));
      }
    } finally {
      const after = snapshot(panel);
      const changed = Object.keys({ ...before, ...after }).filter((k) => before[k] !== after[k]).sort();
      const result = {
        calls: [...calls].sort(), state: changed, events: emitted,
        dom: panel.shadowRoot.innerHTML !== domBefore,
      };
      calls = null;
      panel.dispatchEvent = origDispatch;
      return result;
    }
  };
})();
