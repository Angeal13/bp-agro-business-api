# BP Agro — Business Admin Portal

A modern, non-technical interface for BP Agro administrators to manage clients, farms, and platform-wide statistics.

## Features
- **Overview Dashboard**: Real-time KPIs for the entire ecosystem.
- **Client Management**: Create, update, and delete clients.
- **Farm Tracking**: View all farms across the platform.
- **Unified Design**: Built with the **Nature Tech** design system for a premium experience.

## Deployment
1. **Frontend**: Serve the `frontend/index.html` file using any web server (Nginx, Apache, or AWS S3).
2. **Backend**: Ensure the `bp-agro-business-api` is running and accessible.
3. **Configuration**: Update the `API_BASE` constant in `frontend/index.html` to point to your deployed Global API URL.

## Tech Stack
- **UI**: Vanilla JavaScript / HTML5 / CSS3
- **Icons**: FontAwesome 6.0
- **Fonts**: Space Grotesk, DM Sans, Fira Code
