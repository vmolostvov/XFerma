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
            username: "vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-5daef2b226f74-filter-medium",
            password: "e3ibl6cpq4"
        }
    };
}
chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {urls: ["<all_urls>"]},
        ['blocking']
);