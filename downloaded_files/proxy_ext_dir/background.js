var config = {
    mode: "fixed_servers",
    rules: {
      singleProxy: {
        scheme: "http",
        host: "gate.nodemaven.com",
        port: parseInt("8080")
      },
    bypassList: [""]
    }
  };
chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
function callbackFn(details) {
    return {
        authCredentials: {
            username: "vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-399a85c38e684-filter-medium",
            password: "e3ibl6cpq4"
        }
    };
}
chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {urls: ["<all_urls>"]},
        ['blocking']
);