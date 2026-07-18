FROM node:22-alpine AS development

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]

FROM development AS build

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
