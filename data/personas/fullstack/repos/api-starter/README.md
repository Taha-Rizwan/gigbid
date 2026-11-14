# api-starter

Reusable starter kit for fast‑moving backend projects.  
It gives you:

- **Typed request validation** with Zod  
- **Central error handling** that returns clean JSON errors  
- **Prisma client** pre‑configured for a PostgreSQL database  

The starter was created for a legal‑tech client in September 2021 and has been reused on dozens of SaaS back‑ends.

## Quick start

1. **Clone** the repo  
   ```bash
   git clone https://github.com/mateo-alvarez/api-starter.git
   cd api-starter
   ```

2. **Install** dependencies  
   ```bash
   npm install
   ```

3. **Configure** environment variables (see `.env.example`)  

4. **Run** the dev server  
   ```bash
   npm run dev
   ```

   The API will be available at `http://localhost:3000`.

## Scripts

- `npm run dev` – start the server with `ts-node-dev` (watch mode)  
- `npm test` – run the Vitest suite  

## How it works

- **src/server.ts** creates an Express app, plugs in JSON parsing, the validation middleware, and a global error handler.  
- **src/validation.ts** exports a helper that builds Zod schemas and returns a middleware that validates `req.body`.  
- **src/db.ts** initializes a Prisma client from `DATABASE_URL`.  
- **src/routes.ts** (example) shows a simple CRUD endpoint using the validation helper and Prisma.

Feel free to copy the folder structure into any new project and add your own routes.
