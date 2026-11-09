# Test-only launch after genuine Wayland socket creation; no installed autostart.
case " $($BB cat /proc/cmdline) " in
 *" roko.avatar_fixture=1 "*)
  (
   i=0
   while [ "$i" -lt 120 ]; do
    for socket in /run/user/0/wayland-*; do
     if [ -S "$socket" ]; then
      export WAYLAND_DISPLAY="${socket##*/}"
      $BB sleep 10
      echo ROKO_AVATAR_DIRECT_FIXTURE_LAUNCH
      exec /usr/bin/roko-avatar-test
     fi
    done
    $BB sleep 1; i=$((i + 1))
   done
   echo ROKO_AVATAR_DIRECT_FIXTURE_SOCKET_TIMEOUT
  ) &
 ;;
esac
