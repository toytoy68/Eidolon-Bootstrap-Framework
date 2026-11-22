#!/bin/sh
# Run on TrueNAS as the operator. Uses the existing gateway credential in place.
# Reconnects WALL-E Wi-Fi once; SSH may disconnect during that operation.
# Does not change host-key checking or permissions.
set -eu
sudo docker exec eidolon-collaboration-x399 \
  ssh -o IPQoS=none -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o ConnectTimeout=5 \
  -o UserKnownHostsFile=/run/wall-e-ssh/known_hosts \
  -i /run/wall-e-ssh/id_ed25519_gateway \
  wall-e-projet@192.168.1.105 \
  'sudo -n nmcli --wait 20 connection up uuid bf0849bf-dbe3-4882-82ac-878034510cb3'
