FROM node:20

WORKDIR /app

# Copy package manifests first so npm ci is cached when only source changes
COPY package*.json ./

# --ignore-scripts prevents Prisma's postinstall from downloading ~300 MB of
# engine binaries with no timeout.  Native add-ons are rebuilt explicitly below.
RUN npm ci --ignore-scripts

# Rebuild native modules that need C++ headers (argon2, better-sqlite3)
RUN npm rebuild argon2 better-sqlite3

COPY . .

# Download Prisma engine binaries and generate the client
RUN npm run db:generate

# Build the Next.js app
RUN npm run build

EXPOSE 3000

# On each deploy: push any pending schema migrations then start the server
CMD ["sh", "-c", "CHECKPOINT_DISABLE=1 node node_modules/prisma/build/index.js db push && node_modules/.bin/next start -p ${PORT:-3000}"]
