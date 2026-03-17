# AppArmor profile for Agent Zero containers (Stopoda / Costraca)
# Install: sudo apparmor_parser -r -W security/apparmor-agent.profile
# Apply in docker-compose: security_opt: [apparmor:agent-zero]

#include <tunables/global>

profile agent-zero flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/nameservice>
  #include <abstractions/python>

  # Allow read on most of filesystem (agent needs to analyze files)
  /                           r,
  /**                         r,

  # Restrict writes to agent workspace only
  /a0/workspace/**            rw,
  /a0/output/**               rw,
  /tmp/agent-**               rw,
  /tmp/stopoda/**             rw,
  /tmp/costraca/**            rw,

  # Allow tool execution
  /usr/bin/python3*           ix,
  /usr/bin/bash               ix,
  /bin/sh                     ix,
  /usr/bin/find               ix,
  /usr/bin/ls                 ix,
  /usr/bin/grep               ix,
  /usr/bin/cat                ix,
  /usr/bin/head               ix,
  /usr/bin/tail               ix,
  /usr/bin/wc                 ix,
  /usr/bin/file               ix,
  /usr/bin/strings            ix,
  /usr/bin/xxd                ix,
  /usr/bin/md5sum             ix,
  /usr/bin/sha256sum          ix,
  /usr/bin/rsync              ix,
  /usr/bin/tar                ix,
  /usr/bin/git                ix,

  # Network: allow only internal connections
  network inet  tcp,
  network inet6 tcp,
  # Block raw sockets (prevent network scanning without shell tool)
  deny network raw,
  deny network packet,

  # Deny access to sensitive system paths
  deny /etc/shadow            r,
  deny /etc/gshadow           r,
  deny /root/.ssh/**          rw,
  deny /proc/sysrq-trigger    w,
  deny /proc/sys/**           w,
  deny /sys/**                w,

  # Deny kernel module loading
  deny @{PROC}/sys/kernel/modprobe rw,
  deny /sbin/modprobe         x,
  deny /sbin/insmod           x,

  # Allow capabilities needed for normal operation
  capability setuid,
  capability setgid,
  capability chown,
  capability dac_override,

  # Deny dangerous capabilities
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_module,
  deny capability sys_rawio,
  deny capability mknod,
  deny capability net_admin,
  deny capability net_raw,
}
