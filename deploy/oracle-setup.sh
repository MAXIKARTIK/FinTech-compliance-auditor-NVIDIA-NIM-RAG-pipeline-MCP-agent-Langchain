#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-shot bootstrap for a fresh Oracle Cloud Always Free VM (Ubuntu or Oracle
# Linux, x86 or ARM/Ampere). Installs Docker + the Compose plugin and opens the
# HOST firewall for HTTP/HTTPS.
#
#   IMPORTANT: this only opens the *OS* firewall. You ALSO have to add an
#   Ingress rule for TCP 80 (and 443) to the VCN Security List / NSG in the
#   Oracle Cloud console — see deploy notes in the README. Both layers must
#   allow the traffic or the dashboard is unreachable.
#
# Usage:
#   chmod +x deploy/oracle-setup.sh
#   ./deploy/oracle-setup.sh
#   # then log out/in once (for docker group), then run deploy.sh
# ---------------------------------------------------------------------------
set -euo pipefail

echo "==> [1/3] Installing Docker Engine + Compose plugin (if missing)"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
else
    echo "    docker already installed: $(docker --version)"
fi

# The convenience script installs the compose plugin; verify it.
if ! docker compose version >/dev/null 2>&1; then
    echo "    Installing docker compose plugin explicitly..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -y && sudo apt-get install -y docker-compose-plugin
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y docker-compose-plugin || true
    fi
fi

echo "==> [2/3] Adding '$USER' to the docker group (no sudo needed after re-login)"
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker || true

echo "==> [3/3] Opening the host firewall for TCP 80 and 443"
if command -v ufw >/dev/null 2>&1 && sudo ufw status >/dev/null 2>&1; then
    echo "    Using ufw"
    sudo ufw allow 80/tcp || true
    sudo ufw allow 443/tcp || true
elif command -v firewall-cmd >/dev/null 2>&1 && sudo firewall-cmd --state >/dev/null 2>&1; then
    echo "    Using firewalld (Oracle Linux default)"
    sudo firewall-cmd --permanent --add-service=http
    sudo firewall-cmd --permanent --add-service=https
    sudo firewall-cmd --reload
else
    echo "    Using iptables (Ubuntu on Oracle default)"
    # Insert at the top so these ACCEPTs come before Oracle's catch-all REJECT.
    sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
    sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
    # Persist across reboots.
    if command -v netfilter-persistent >/dev/null 2>&1; then
        sudo netfilter-persistent save
    else
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent || true
        sudo netfilter-persistent save || sudo sh -c 'iptables-save > /etc/iptables/rules.v4' || true
    fi
fi

echo ""
echo "=========================================================================="
echo " Host bootstrap complete."
echo "   1) Log out and back in (so the 'docker' group applies to your shell)."
echo "   2) In the Oracle Cloud console, add a VCN Security List / NSG Ingress"
echo "      rule: Source 0.0.0.0/0, TCP, destination port 80 (and 443)."
echo "   3) Run:  ./deploy/deploy.sh"
echo "=========================================================================="
