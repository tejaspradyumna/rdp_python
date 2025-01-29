let ws = null
let hasControl = false
const canvas = document.getElementById("remoteScreen")
const ctx = canvas.getContext("2d")
let serverWidth = 0
let serverHeight = 0
const pressedKeys = new Set()

// Import pako library.  This assumes pako is available via a script tag or a module import.
// Adjust as needed for your project setup.  For example, if using a module bundler like Webpack or Parcel:
// import pako from 'pako';

function connect() {
  ws = new WebSocket(`ws://${window.location.hostname}:8080`)
  ws.binaryType = "arraybuffer"

  ws.onopen = () => {
    console.log("Connected to server")
    setupInputHandlers()
  }

  ws.onmessage = async (event) => {
    if (typeof event.data === "string") {
      const data = JSON.parse(event.data)
      if (data.type === "resolution") {
        serverWidth = data.width
        serverHeight = data.height
        updateCanvasSize(data.width, data.height)
      }
    } else {
      try {
        const frameData = new Uint8Array(event.data)
        const decompressed = pako.inflate(frameData) // pako is now used here
        const blob = new Blob([decompressed], { type: "image/jpeg" })
        const img = await createImageBitmap(blob)
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      } catch (error) {
        console.error("Error rendering frame:", error)
      }
    }
  }

  ws.onclose = () => {
    console.log("Connection closed, reconnecting...")
    setTimeout(connect, 3000)
  }
}

function updateCanvasSize(serverWidth, serverHeight) {
  const maxWidth = window.innerWidth - 40
  const maxHeight = window.innerHeight - 100
  const aspect = serverWidth / serverHeight

  let width = Math.min(serverWidth, maxWidth)
  let height = width / aspect

  if (height > maxHeight) {
    height = maxHeight
    width = height * aspect
  }

  canvas.width = width
  canvas.height = height
}

function getScaledCoordinates(clientX, clientY) {
  const rect = canvas.getBoundingClientRect()
  return {
    x: Math.round((clientX - rect.left) * (serverWidth / canvas.width)),
    y: Math.round((clientY - rect.top) * (serverHeight / canvas.height)),
  }
}

function mapSpecialKey(e) {
  const specialKeys = {
    Tab: "\t",
    Enter: "\n",
    Backspace: "\b",
    Delete: "<delete>",
    Escape: "<esc>",
    ArrowLeft: "<left>",
    ArrowRight: "<right>",
    ArrowUp: "<up>",
    ArrowDown: "<down>",
    Home: "<home>",
    End: "<end>",
    PageUp: "<pageup>",
    PageDown: "<pagedown>",
    Insert: "<insert>",
    Meta: "<windows>",
    ContextMenu: "<menu>",
    PrintScreen: "<printscreen>",
    ScrollLock: "<scrolllock>",
    Pause: "<pause>",
    CapsLock: "<capslock>",
    NumLock: "<numlock>",
    F1: "<f1>",
    F2: "<f2>",
    F3: "<f3>",
    F4: "<f4>",
    F5: "<f5>",
    F6: "<f6>",
    F7: "<f7>",
    F8: "<f8>",
    F9: "<f9>",
    F10: "<f10>",
    F11: "<f11>",
    F12: "<f12>",
  }

  let key = e.key
  const modifiers = []

  if (e.ctrlKey && key !== "Control") modifiers.push("ctrl")
  if (e.altKey && key !== "Alt") modifiers.push("alt")
  if (e.shiftKey && key !== "Shift") modifiers.push("shift")
  if (e.metaKey && key !== "Meta") modifiers.push("windows")

  if (specialKeys[key]) {
    key = specialKeys[key]
  } else if (key.length === 1) {
    key = e.key;
  }

  return modifiers.length > 0 ? `<${modifiers.join("+")}+${key}>` : key
}

function setupInputHandlers() {
  canvas.addEventListener("contextmenu", (e) => e.preventDefault())

  canvas.addEventListener(
    "mousedown",
    (e) => {
      if (!hasControl) return
      e.preventDefault()
      const { x, y } = getScaledCoordinates(e.clientX, e.clientY)
      ws.send(JSON.stringify({ type: "mouse_down", x, y, button: e.button + 1 }))
    },
    { passive: false },
  )

  canvas.addEventListener(
    "mouseup",
    (e) => {
      if (!hasControl) return
      e.preventDefault()
      const { x, y } = getScaledCoordinates(e.clientX, e.clientY)
      ws.send(JSON.stringify({ type: "mouse_up", x, y, button: e.button + 1 }))
    },
    { passive: false },
  )

  canvas.addEventListener("mousemove", (e) => {
    if (!hasControl) return
    const { x, y } = getScaledCoordinates(e.clientX, e.clientY)
    ws.send(JSON.stringify({ type: "mouse_move", x, y }))
  })

  canvas.addEventListener(
    "wheel",
    (e) => {
      if (!hasControl) return
      e.preventDefault()
      const { x, y } = getScaledCoordinates(e.clientX, e.clientY)
      ws.send(JSON.stringify({ type: "mouse_wheel", x, y, delta: Math.sign(e.deltaY) * -120 }))
    },
    { passive: false },
  )

  window.addEventListener(
    "keydown",
    (e) => {
      if (!hasControl) return
      if (e.target === document.body || e.target === canvas) {
        e.preventDefault()
        const keyCode = `${e.code}-${e.key}`
        if (!pressedKeys.has(keyCode)) {
          pressedKeys.add(keyCode)
          ws.send(JSON.stringify({ type: "keyboard", key: mapSpecialKey(e), action: "down" }))
        }
      }
    },
    true,
  )

  window.addEventListener(
    "keyup",
    (e) => {
      if (!hasControl) return
      if (e.target === document.body || e.target === canvas) {
        e.preventDefault()
        const keyCode = `${e.code}-${e.key}`
        pressedKeys.delete(keyCode)
        ws.send(JSON.stringify({ type: "keyboard", key: mapSpecialKey(e), action: "up" }))
      }
    },
    true,
  )

  window.addEventListener("blur", () => {
    pressedKeys.clear()
  })

  window.addEventListener(
    "keydown",
    (e) => {
      if (hasControl && (e.ctrlKey || e.altKey || e.metaKey)) {
        e.preventDefault()
      }
    },
    true,
  )
}

function toggleControl(state) {
  hasControl = state
  ws.send(JSON.stringify({ type: "control_state", state }))
  canvas.style.cursor = state ? "none" : "default"
  if (state) {
    canvas.focus()
  } else {
    canvas.blur()
    pressedKeys.clear()
  }
}

// Add these functions to handle the Take Control and Release Control buttons
function takeControl() {
  toggleControl(true)
  canvas.focus()
}

function releaseControl() {
  toggleControl(false)
  canvas.blur()
}

connect()

// Make sure to add these event listeners to your Take Control and Release Control buttons
document.getElementById("takeControlBtn").addEventListener("click", takeControl)
document.getElementById("releaseControlBtn").addEventListener("click", releaseControl)

