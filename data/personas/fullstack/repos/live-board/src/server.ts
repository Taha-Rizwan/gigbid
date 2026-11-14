import http from 'http';
import express from 'express';
import { Server as SocketIOServer } from 'socket.io';
import Redis from 'ioredis';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] },
});

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const redisPub = new Redis(REDIS_URL);
const redisSub = new Redis(REDIS_URL);

/**
 * Broadcast a location update to all connected clients.
 * Payload shape: { truckId: string, lat: number, lng: number, loadId?: string }
 */
function broadcastUpdate(update: any) {
  io.emit('location:update', update);
  redisPub.publish('dispatch:updates', JSON.stringify(update));
}

// Listen for updates from other server instances
redisSub.subscribe('dispatch:updates', (err, count) => {
  if (err) {
    console.error('Failed to subscribe to Redis channel', err);
    return;
  }
  console.log(`Subscribed to ${count} Redis channel(s).`);
});

redisSub.on('message', (channel, message) => {
  if (channel === 'dispatch:updates') {
    const update = JSON.parse(message);
    io.emit('location:update', update);
  }
});

// Socket.IO connection handling
io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  socket.on('location:update', (data) => {
    // Validate minimal fields
    if (data.truckId && typeof data.lat === 'number' && typeof data.lng === 'number') {
      broadcastUpdate(data);
    }
  });

  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
  });
});

const PORT = parseInt(process.env.PORT ?? '3000', 10);
server.listen(PORT, () => {
  console.log(`Dispatch server listening on port ${PORT}`);
});
