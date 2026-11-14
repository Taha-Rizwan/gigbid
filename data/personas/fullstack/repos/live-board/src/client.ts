import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { io, Socket } from 'socket.io-client';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import dotenv from 'dotenv';

dotenv.config();

const SOCKET_URL = process.env.SOCKET_URL || 'http://localhost:3000';
const MAPBOX_TOKEN = process.env.MAPBOX_TOKEN ?? '';

interface Truck {
  truckId: string;
  lat: number;
  lng: number;
  loadId?: string;
}

/**
 * Main map component that renders trucks as markers and updates them in real time.
 */
function DispatchMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<mapboxgl.Map>();
  const socketRef = useRef<Socket>();
  const [trucks, setTrucks] = useState<Record<string, mapboxgl.Marker>>({});

  // Initialize Mapbox map
  useEffect(() => {
    if (!MAPBOX_TOKEN) {
      console.error('Mapbox token missing');
      return;
    }
    if (mapContainer.current && !mapInstance.current) {
      mapboxgl.accessToken = MAPBOX_TOKEN;
      mapInstance.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: 'mapbox://styles/mapbox/streets-v11',
        center: [-98.35, 39.5],
        zoom: 4,
      });
    }
  }, []);

  // Setup Socket.IO connection
  useEffect(() => {
    const socket = io(SOCKET_URL);
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Connected to dispatch server');
    });

    socket.on('location:update', (data: Truck) => {
      const { truckId, lat, lng } = data;
      if (!mapInstance.current) return;

      // Update existing marker or create a new one
      setTrucks((prev) => {
        const markers = { ...prev };
        if (markers[truckId]) {
          markers[truckId].setLngLat([lng, lat]);
        } else {
          const el = document.createElement('div');
          el.className = 'truck-marker';
          el.style.width = '20px';
          el.style.height = '20px';
          el.style.backgroundColor = '#ff5722';
          el.style.borderRadius = '50%';
          const marker = new mapboxgl.Marker(el).setLngLat([lng, lat]).addTo(mapInstance.current!);
          markers[truckId] = marker;
        }
        return markers;
      });
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  return <div ref={mapContainer} style={{ width: '100vw', height: '100vh' }} />;
}

// Render the app
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<DispatchMap />);
}
