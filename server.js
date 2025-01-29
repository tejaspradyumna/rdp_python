const net = require('net');
const express = require('express');
const WebSocket = require('ws');
const path = require('path');

// Configuration
const RELAY_PORT = 5000;
const HTTP_PORT = 3000;
const WS_PORT = 8080;
const RELAY_IP = '0.0.0.0';

// TCP Relay Server
const tcpServer = net.createServer((socket) => {
    let clientType = null;
    let pairedSocket = null;
    let buffer = Buffer.alloc(0);

    socket.on('data', (data) => {
        if (!clientType) {
            const message = data.toString().trim();
            if (message === 'host') {
                clientType = 'host';
                tcpServer.hostSocket = socket;
                buffer = buffer.subarray(5); // Remove 'host' message
                console.log('Host connected');
                
                // Forward any initial data
                if (buffer.length > 0 && tcpServer.clientSocket) {
                    tcpServer.clientSocket.write(buffer);
                }
            } else if (message === 'client') {
                clientType = 'client';
                tcpServer.clientSocket = socket;
                buffer = buffer.subarray(6); // Remove 'client' message
                console.log('Client connected');
                
                if (tcpServer.hostSocket) {
                    // Forward buffered data to host
                    tcpServer.hostSocket.write(buffer);
                }
            }
            return;
        }

        // Forward data to paired connection
        if (clientType === 'host' && tcpServer.clientSocket) {
            tcpServer.clientSocket.write(data);
        } else if (clientType === 'client' && tcpServer.hostSocket) {
            tcpServer.hostSocket.write(data);
        }
    });

    function setupBidirectionalForwarding(s1, s2) {
        s1.on('data', (data) => s2.write(data));
        s2.on('data', (data) => s1.write(data));
        s1.on('close', () => s2.end());
        s2.on('close', () => s1.end());
    }

    socket.on('error', (err) => console.error('Relay error:', err));
});

tcpServer.listen(RELAY_PORT, RELAY_IP, () => {
    console.log(`TCP Relay running on ${RELAY_IP}:${RELAY_PORT}`);
});

// Web Server
const app = express();
app.use(express.static(path.join(__dirname, 'public')));

const httpServer = app.listen(HTTP_PORT, () => {
    console.log(`HTTP server running on port ${HTTP_PORT}`);
});

// WebSocket Server
const wss = new WebSocket.Server({ port: WS_PORT });

wss.on('connection', (ws) => {
    console.log('New WebSocket client connected');
    let tcpClient = new net.Socket();
    let buffer = Buffer.alloc(0);
    let expectedLength = 4;
    let isReadingFrame = false;

    tcpClient.connect(RELAY_PORT, RELAY_IP, () => {
        tcpClient.write('client');
    });

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            const encodedMessage = encodeMessage(data);
            tcpClient.write(encodedMessage);
        } catch (error) {
            console.error('Error processing message:', error);
        }
    });

    tcpClient.on('data', (data) => {
        buffer = Buffer.concat([buffer, data]);
        
        while (buffer.length >= expectedLength) {
            if (!isReadingFrame) {
                const frameLength = buffer.readUInt32BE(0);
                buffer = buffer.subarray(4);
                expectedLength = frameLength;
                isReadingFrame = true;
            } else {
                const frameData = buffer.subarray(0, expectedLength);
                buffer = buffer.subarray(expectedLength);
                
                if (frameData.toString().startsWith('RES:')) {
                    const [width, height] = frameData.toString().split(':')[1].split(',').map(Number);
                    ws.send(JSON.stringify({ type: 'resolution', width, height }));
                } else {
                    ws.send(frameData);
                }
                
                expectedLength = 4;
                isReadingFrame = false;
            }
        }
    });

    const cleanup = () => tcpClient.destroy();
    ws.on('close', cleanup);
    tcpClient.on('close', () => ws.close());
    tcpClient.on('error', cleanup);
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