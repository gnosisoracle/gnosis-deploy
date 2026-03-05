#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Detecting OS..."
uname -a
cat /etc/os-release 2>/dev/null || true

echo "==> Installing Chrome via multiple methods..."

# Method 1: Direct .deb download (most reliable on Render)
echo "--- Method 1: Direct .deb ---"
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb && \
  apt-get install -y -qq /tmp/chrome.deb && \
  echo "Method 1 SUCCESS" || echo "Method 1 failed"

echo "==> Locating Chrome binary..."
which google-chrome-stable 2>/dev/null && echo "Found: google-chrome-stable" || true
which google-chrome 2>/dev/null && echo "Found: google-chrome" || true
ls /usr/bin/google-chrome* 2>/dev/null || true
ls /opt/google/chrome/ 2>/dev/null || true

echo "==> Chrome version..."
google-chrome-stable --version 2>/dev/null || \
google-chrome --version 2>/dev/null || \
echo "Chrome not in PATH — check /opt/google/chrome/"

echo "==> Build complete."
