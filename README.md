# Family Location App

A consent-based family location-sharing application built with Python, Flask, PostgreSQL, and Android.

## Overview

Family Location App allows authorized family members to share their device locations and view recent location updates through a web dashboard.

The project demonstrates backend development, database integration, API authentication, and Android-to-server communication.

## Features

- Family login protected by a shared password
- Location-sharing interface and dashboard
- Android location updates through an authenticated API
- PostgreSQL storage for location records
- Automatic updating of existing location records
- Validation of location coordinates and accuracy values
- Expiration of old location updates after 120 seconds
- Manual location-sharing controls in the Android app

## Technology Stack

- **Backend:** Python, Flask
- **Database:** PostgreSQL
- **Android:** Kotlin
- **Location services:** Google Play Services Location
- **Map:** Leaflet and OpenStreetMap
- **Hosting:** Render
- **Version control:** Git and GitHub

## Architecture

1. The Android app obtains location updates after the user enables sharing.
2. The app sends location data to the Flask backend through an authenticated HTTP API.
3. The backend validates incoming data and stores the latest location in PostgreSQL.
4. The web dashboard retrieves and displays recent location information.

## Privacy and Security

Location sharing is intended for consenting family members. Sharing should be controlled by the device user.

Credentials and secret configuration values must be supplied through environment variables and must not be committed to the repository.

The Android authentication token is included in the built application and should not be considered a secret that cannot be extracted.

## Project Status

The backend is deployed on Render, and the Android app has been tested with the hosted service.

## Future Improvements

- Stronger individual user authentication
- More robust credential management
- Improved location-sharing status and error handling
- Additional testing and documentation

## Developer

GitHub: https://github.com/aditiroy7116
