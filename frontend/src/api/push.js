// 推送初始化：仅在 Capacitor 原生环境（App）内执行，浏览器里跳过
export async function initPush(api) {
  if (typeof window === 'undefined') return;
  if (!window.Capacitor?.isNativePlatform?.()) return;

  const { PushNotifications } = await import('@capacitor/push-notifications');

  try {
    let perm = await PushNotifications.checkPermissions();
    if (perm.receive === 'prompt') {
      perm = await PushNotifications.requestPermissions();
    }
    if (perm.receive !== 'granted') return;

    await PushNotifications.register();

    PushNotifications.addListener('registration', (token) => {
      api.registerPushToken(token.value).catch(() => {});
    });

    PushNotifications.addListener('registrationError', () => {});

    // 用户点推送 → 深链跳转
    PushNotifications.addListener('pushNotificationActionPerformed', (n) => {
      const url = n.notification?.data?.url;
      if (url) window.location.hash = url;
    });
  } catch (e) {
    // 推送初始化失败不影响主流程
  }
}
