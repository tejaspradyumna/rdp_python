// server.js
const express = require('express');
const WebSocket = require('ws');
const net = require('net');
const path = require('path');

const app = express();
const HTTP_PORT = 3000;
const WS_PORT = 8080;

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// HTTP serverss
const server = app.listen(HTTP_PORT, () => {
    console.log(`HTTP server running on port ${HTTP_PORT}`);
});

// WebSocket server
const wss = new WebSocket.Server({ port: WS_PORT });

wss.on('connection', (ws) => {
    console.log('New WebSocket client connected');
    let tcpClient = new net.Socket();
    let buffer = Buffer.alloc(0);
    let expectedLength = 4;
    let isReadingFrame = false;

    // Connect to Python server
    tcpClient.connect(5000, '192.168.1.137', () => {
        console.log('Connected to Python desktop server');
    });

    // Handle WebSocket messages from browser
    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            const encodedMessage = encodeMessage(data);
            tcpClient.write(encodedMessage);
        } catch (error) {
            console.error('Error processing message:', error);
        }
    });

    // Handle TCP data from Python
    tcpClient.on('data', (data) => {
        buffer = Buffer.concat([buffer, data]);
        
        while (buffer.length >= expectedLength) {
            if (!isReadingFrame) {
                // Reading header
                const frameLength = buffer.readUInt32BE(0);
                buffer = buffer.subarray(4);
                expectedLength = frameLength;
                isReadingFrame = true;
            } else {
                // Reading frame data
                const frameData = buffer.subarray(0, expectedLength);
                buffer = buffer.subarray(expectedLength);
                
                if (frameData.toString().startsWith('RES:')) {
                    // Handle resolution info
                    const [width, height] = frameData.toString().split(':')[1].split(',').map(Number);
                    ws.send(JSON.stringify({ type: 'resolution', width, height }));
                } else {
                    // Handle frame data
                    ws.send(frameData);
                }
                
                expectedLength = 4;
                isReadingFrame = false;
            }
        }
    });

    // Handle connection cleanup
    const cleanup = () => {
        if (tcpClient) {
            tcpClient.destroy();
        }
    };

    ws.on('close', cleanup);
    tcpClient.on('close', () => {
        console.log('TCP connection closed');
        ws.close();
    });
    tcpClient.on('error', (error) => {
        console.error('TCP error:', error);
        cleanup();
    });
});

function encodeMessage(data) {
    const messageTypes = {
        mouse_move: 1,
        mouse_down: 4,
        mouse_up: 5,
        keyboard: 3,
        mouse_wheel: 6,
        control_state: 7
    };

    const type = messageTypes[data.type];
    let payload = '';

    switch (data.type) {
        case 'mouse_move':
            payload = `${data.x},${data.y}`;
            break;
        case 'mouse_down':
        case 'mouse_up':
            payload = `${data.x},${data.y},${data.button}`;
            break;
        case 'keyboard':
            payload = data.key;
            break;
        case 'mouse_wheel':
            payload = `${data.x},${data.y},${data.delta}`;
            break;
        case 'control_state':
            payload = data.state ? '1' : '0';
            break;
    }

    const header = Buffer.alloc(5);
    header.writeUInt8(type, 0);
    header.writeUInt32BE(payload.length, 1);
    return Buffer.concat([header, Buffer.from(payload)]);
}