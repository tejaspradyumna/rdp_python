let ws = null;
let hasControl = false;
const canvas = document.getElementById("remoteScreen");
const ctx = canvas.getContext("2d");
let serverWidth = 0;
let serverHeight = 0;
const pressedKeys = new Set();

function connect() {
    ws = new WebSocket(`ws://${window.location.hostname}:8080`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        console.log("Connected to server");
        setupInputHandlers();
    };

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
          // Handle resolution message
          const data = JSON.parse(event.data);
          if (data.type === "resolution") {
              serverWidth = data.width;
              serverHeight = data.height;
              updateCanvasSize(data.width, data.height);
          }
      } else {
          // Handle binary frame data
          try {
              const frameData = new Uint8Array(event.data);
              const decompressed = pako.inflate(frameData);
              const blob = new Blob([decompressed], { type: "image/jpeg" });
              const img = await createImageBitmap(blob);
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          } catch (error) {
              console.error("Frame processing error:", error);
          }
      }
  };

    ws.onclose = () => {
        console.log("Connection closed, reconnecting...");
        setTimeout(connect, 3000);
    };
}

function updateCanvasSize(width, height) {
    const maxWidth = window.innerWidth - 40;
    const maxHeight = window.innerHeight - 100;
    const aspect = width / height;

    let newWidth = Math.min(width, maxWidth);
    let newHeight = newWidth / aspect;

    if (newHeight > maxHeight) {
        newHeight = maxHeight;
        newWidth = newHeight * aspect;
    }

    canvas.width = newWidth;
    canvas.height = newHeight;
}

function getScaledCoordinates(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: Math.round((clientX - rect.left) * (serverWidth / canvas.width)),
        y: Math.round((clientY - rect.top) * (serverHeight / canvas.height))
    };
}

function mapSpecialKey(e) {
    const specialMap = {
        'Tab': '\t', 'Enter': '\n', 'Backspace': '\b',
        'Escape': '\x1b', 'ArrowLeft': '<left>', 'ArrowRight': '<right>',
        'ArrowUp': '<up>', 'ArrowDown': '<down>', 'Home': '<home>',
        'End': '<end>', 'PageUp': '<pageup>', 'PageDown': '<pagedown>'
    };

    let key = specialMap[e.key] || e.key;
    const modifiers = [];
    if (e.ctrlKey) modifiers.push('ctrl');
    if (e.altKey) modifiers.push('alt');
    if (e.shiftKey) modifiers.push('shift');
    if (e.metaKey) modifiers.push('meta');

    return modifiers.length > 0 ? `<${modifiers.join('+')}+${key}>` : key;
}

function setupInputHandlers() {
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());

    const sendEvent = (type, e, extra = {}) => {
        if (!hasControl) return;
        e.preventDefault();
        const { x, y } = getScaledCoordinates(e.clientX, e.clientY);
        ws.send(JSON.stringify({ type, x, y, ...extra }));
    };

    canvas.addEventListener("mousedown", (e) => 
        sendEvent("mouse_down", e, { button: e.button + 1 }));
    canvas.addEventListener("mouseup", (e) => 
        sendEvent("mouse_up", e, { button: e.button + 1 }));
    canvas.addEventListener("mousemove", (e) => 
        sendEvent("mouse_move", e));
    canvas.addEventListener("wheel", (e) => 
        sendEvent("mouse_wheel", e, { delta: Math.sign(e.deltaY) * -120 }));

    window.addEventListener("keydown", (e) => {
        if (!hasControl || pressedKeys.has(e.code)) return;
        pressedKeys.add(e.code);
        ws.send(JSON.stringify({ 
            type: "keyboard", 
            key: mapSpecialKey(e), 
            action: "down" 
        }));
    });

    window.addEventListener("keyup", (e) => {
        if (!hasControl) return;
        pressedKeys.delete(e.code);
        ws.send(JSON.stringify({ 
            type: "keyboard", 
            key: mapSpecialKey(e), 
            action: "up" 
        }));
    });

    window.addEventListener("blur", () => pressedKeys.clear());
}

function toggleControl(state) {
    hasControl = state;
    ws.send(JSON.stringify({ type: "control_state", state }));
    canvas.style.cursor = state ? "none" : "default";
    state ? canvas.focus() : canvas.blur();
}

document.getElementById("takeControl").addEventListener("click", () => toggleControl(true));
document.getElementById("releaseControl").addEventListener("click", () => toggleControl(false));

connect();