# X399 native migration — 2026-11-06

The remote DARME reader treated a complete SSH response as unavailable when stdout
closed before the SSH process delivered its exit status. Four live attempts ended
with SIGKILL (-9). A regression that closes stdout before a delayed successful exit
failed before the correction.

The reader now waits for process exit within the original deadline after EOF.
Timeout, excessive output and unsuccessful exit remain failures. The regression
also checks delayed failure and a process that hangs after EOF.

Validation: 34 monitor tests passed, including forced-command restrictions and the
EOF regression. Operational rollout uses the existing restricted Memory feed.
No browser-controlled SSH arguments or additional remote commands were introduced.

Migration configuration and credentials stay outside Git. The deployed DARME
package retains the previously deployed TLS collector and now monitors the native
host and Memory services. The host has automatic NTP and a UTC hardware clock.
