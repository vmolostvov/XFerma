import requests
import json


class TwitterFrontendFlow:
    def __init__(self, proxies={}, language="en"):
        self.USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        self.AUTHORIZATION = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
        self.proxies = proxies
        self.session = requests.session()
        self.__twitter()
        self.x_guest_token = self.__get_guest_token()
        self.method_check_bypass = False
        self.flow_token = None
        self.language = language

    def __twitter(self):
        headers = {
            "User-Agent": self.USER_AGENT,
        }
        response = self.session.get(
            "https://x.com/", headers=headers, proxies=self.proxies
        )
        return self

    def __get_guest_token(self):
        headers = {
            "authorization": self.AUTHORIZATION,
            "User-Agent": self.USER_AGENT,
        }
        response = self.session.post(
            "https://api.x.com/1.1/guest/activate.json",
            headers=headers,
            proxies=self.proxies,
        ).json()
        return response["guest_token"]

    def __get_headers(self):
        return {
            "authorization": self.AUTHORIZATION,
            "User-Agent": self.USER_AGENT,
            "Content-type": "application/json",
            "x-guest-token": self.x_guest_token,
            "x-csrf-token": self.session.cookies.get("ct0"),
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": self.language,
        }

    def __get_headers_legacy(self):
        return {
            "authorization": self.AUTHORIZATION,
            "User-Agent": self.USER_AGENT,
            "Content-type": "application/x-www-form-urlencoded",
            "x-csrf-token": self.session.cookies.get("ct0"),
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
        }

    def get_subtask_ids(self):
        return [subtasks["subtask_id"] for subtasks in self.content["subtasks"]]

    def __flow_token_check(self):
        if self.flow_token == None:
            raise Exception("not found token")

    def __error_check(self, content):
        if content.get("errors"):
            raise Exception(content["errors"][0]["message"])

    def __method_check(self, method_name):
        if self.method_check_bypass:
            return
        if method_name not in self.get_subtask_ids():
            raise Exception(
                "{0} is inappropriate method. choose from {1}. information: https://github.com/fa0311/TwitterFrontendFlow#inappropriate-method".format(
                    method_name, ", ".join(self.get_subtask_ids())
                )
            )

    def LoadCookies(self, file_path):
        with open(file_path, "r") as f:
            for cookie in json.load(f):
                self.session.cookies.set_cookie(
                    requests.cookies.create_cookie(**cookie)
                )
        return self

    def SaveCookies(self, file_path):
        cookies = []
        for cookie in self.session.cookies:
            cookie_dict = dict(
                version=cookie.version,
                name=cookie.name,
                value=cookie.value,
                port=cookie.port,
                domain=cookie.domain,
                path=cookie.path,
                secure=cookie.secure,
                expires=cookie.expires,
                discard=cookie.discard,
                comment=cookie.comment,
                comment_url=cookie.comment_url,
                rfc2109=cookie.rfc2109,
                rest=cookie._rest,
            )
            cookies.append(cookie_dict)

        with open(file_path, "w") as f:
            json.dump(cookies, f, indent=4)
        return self

    # ログイン

    def login_flow(self):
        data = {
            "input_flow_data": {
                "flow_context": {
                    "debug_overrides": {},
                    "start_location": {"location": "manual_link"},
                }
            },
            "subtask_versions": {
                "action_list": 2,
                "alert_dialog": 1,
                "app_download_cta": 1,
                "check_logged_in_account": 1,
                "choice_selection": 3,
                "contacts_live_sync_permission_prompt": 0,
                "cta": 7,
                "email_verification": 2,
                "end_flow": 1,
                "enter_date": 1,
                "enter_email": 2,
                "enter_password": 5,
                "enter_phone": 2,
                "enter_recaptcha": 1,
                "enter_text": 5,
                "enter_username": 2,
                "generic_urt": 3,
                "in_app_notification": 1,
                "interest_picker": 3,
                "js_instrumentation": 1,
                "menu_dialog": 1,
                "notifications_permission_prompt": 2,
                "open_account": 2,
                "open_home_timeline": 1,
                "open_link": 1,
                "phone_verification": 4,
                "privacy_options": 1,
                "security_key": 3,
                "select_avatar": 4,
                "select_banner": 2,
                "settings_list": 7,
                "show_code": 1,
                "sign_up": 2,
                "sign_up_review": 4,
                "tweet_selection_urt": 1,
                "update_users": 1,
                "upload_media": 1,
                "user_recommendations_list": 4,
                "user_recommendations_urt": 1,
                "wait_spinner": 3,
                "web_modal": 1
            },
        }
        params = {"flow_name": "login"}
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            params=params,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginJsInstrumentationSubtask(self):
        self.__flow_token_check()
        self.__method_check("LoginJsInstrumentationSubtask")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginJsInstrumentationSubtask",
                    "js_instrumentation": {
                        "response": json.dumps(
                            {
                                "rf": {
                                    "ec2dd29fc4a651efa258a6d8ee80882756a7baa8584420bd2eb17457f9344a22": -1,
                                    "aa1d709ed9884c2954bf64630edc4571dc03d70f27392289e0208d5273e37d91": -132,
                                    "add94acd2cd14239adef2a2609477207a229d67ac6690921dd6ac76e5f93bdb7": -138,
                                    "a79ff8bf51ea041fc878f1f82d3ab54e0aec833e4d9166652c9e504766a505f1": 187,
                                },
                                "s": "Z4Z0ziwX2n8dGFypz52losLlgzT6tNk932kgp9LAOMfo87oDQpXFGjT9lwY6-Ef_zdBObdKKshS1ozgL_dWCkZOpbxyKShK0vjk2S9__KwoZHSNOvMHROAFPAcHIVaPgfPingn9qY1E7-vzQpRpfS3Mr6gbZIS__hmt-NIRfYbCFhZPMU-AAsKDYkidZr8CCXr6dFQGESg3wjXWc3OCvLV-QmyeteJ3omzSmj6YGCbY1V6ikhRcDc-6FAhRyZ5NdXj47MDzpJmzqyyeyya0gM2wY7dQPBSBNXPcXSbQ9F5yz4CsyaL0D7WZybnUDVJ6cSBnPkEEgnhCB-1xwmSYEzQAAAZs_HPwu",
                            }
                        ),
                        "link": "next_link",
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginEnterUserIdentifierSSO(self, user_id):
        self.__flow_token_check()
        self.__method_check("LoginEnterUserIdentifierSSO")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginEnterUserIdentifierSSO",
                    "settings_list": {
                        "setting_responses": [
                            {
                                "key": "user_identifier",
                                "response_data": {"text_data": {"result": user_id}},
                            }
                        ],
                        "link": "next_link",
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def AccountDuplicationCheck(self):
        self.__flow_token_check()
        self.__method_check("AccountDuplicationCheck")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "AccountDuplicationCheck",
                    "check_logged_in_account": {
                        "link": "AccountDuplicationCheck_false"
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginEnterAlternateIdentifierSubtask(self, text):
        self.__flow_token_check()
        self.__method_check("LoginEnterAlternateIdentifierSubtask")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginEnterAlternateIdentifierSubtask",
                    "enter_text": {"text": text, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginEnterPassword(self, password):
        self.__flow_token_check()
        self.__method_check("LoginEnterPassword")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginEnterPassword",
                    "enter_password": {"password": password, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginTwoFactorAuthChallenge(self, TwoFactorCode):
        self.__flow_token_check()
        self.__method_check("LoginTwoFactorAuthChallenge")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginTwoFactorAuthChallenge",
                    "enter_text": {"text": TwoFactorCode, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginAcid(self, acid):
        self.__flow_token_check()
        self.__method_check("LoginAcid")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "LoginAcid",
                    "enter_text": {"text": acid, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def LoginAcid(self, acid):
        self.__flow_token_check()
        self.__method_check("LoginAcid")
        data = {
            "flow_token":self.flow_token,
            "subtask_inputs":[
                {
                    "subtask_id":"LoginAcid",
                    "enter_text":
                        {
                            "text": acid,
                            "link":"next_link"
                        }
                    }
                ]
            }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.flow_token = response.get("flow_token")
        self.content = response
        self.__error_check()
        return self


    # attの取得 無くても動くっぽい

    def get_att(self):
        data = {"flow_token": self.flow_token, "subtask_inputs": []}
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    # ct0の更新 無くても動くっぽい

    def Viewer(self):
        params = {
            "variables": json.dumps(
                {
                    "withCommunitiesMemberships": True,
                    "withCommunitiesCreation": True,
                    "withSuperFollowsUserFields": True,
                }
            )
        }
        response = self.session.get(
            "https://api.x.com/graphql/O_C5Q6xAVNOmeolcXjKqYw/Viewer",
            headers=self.__get_headers(),
            params=params,
        )
        self.__error_check(response)
        self.content = response
        return self

    def RedirectToPasswordReset(self):
        raise Exception(
            "RedirectToPasswordResetは現在サポートされていません。代わりにpassword_reset_flowを使用して下さい。"
        )

    # パスワードリセット

    def password_reset_flow(self):
        data = {
            "input_flow_data": {
                "flow_context": {
                    "debug_overrides": {},
                    "start_location": {"location": "manual_link"},
                }
            },
            "subtask_versions": {
                "contacts_live_sync_permission_prompt": 0,
                "email_verification": 1,
                "topics_selector": 1,
                "wait_spinner": 1,
                "cta": 4,
            },
        }
        params = {"flow_name": "password_reset"}
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            params=params,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PwrJsInstrumentationSubtask(self):
        self.__flow_token_check()
        self.__method_check("PwrJsInstrumentationSubtask")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PwrJsInstrumentationSubtask",
                    "js_instrumentation": {
                        "response": json.dumps(
                            {
                                "rf": {
                                    "af07339bbc6d24ced887d705eb0c9fd29b4a7d7ddc21136c9f94d53a4bc774d2": 88,
                                    "a6ce87d6481c6ec4a823548be3343437888441d2a453061c54f8e2eb325856f7": 250,
                                    "a0062ad06384a8afd38a41cd83f31b0dbfdea0eff4b24c69f0dd9095b2fb56d6": 16,
                                    "a929e5913a5715d93491eaffaa139ba4977cbc826a5e2dbcdc81cae0f093db25": 186,
                                },
                                "s": "Q-H-53m1uXImK0F0ogrxRQtCWTH1KIlPbIy0MloowlMa4WNK5ZCcDoXyRs1q_cPbynK73w_wfHG_UVRKKBWRoh6UJtlPS5kMa1p8fEvTYi76hwdzBEzovieR8t86UpeSkSBFYcL8foYKSp6Nop5mQR_QHGyEeleclCPUvzS0HblBJqZZdtUo-6by4BgCyu3eQ4fY5nOF8fXC85mu6k34wo982LMK650NsoPL96DBuloqSZvSHU47wq2uA4xy24UnI2WOc6U9KTvxumtchSYNnXq1HV662B8U2-jWrzvIU4yUHV3JYUO6sbN6j8Ho9JaUNJpJSK7REwqCBQ3yG7iwMAAAAX2Vqcbs",
                            }
                        ),
                        "link": "next_link",
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PasswordResetBegin(self, user_id):
        self.__flow_token_check()
        self.__method_check("PasswordResetBegin")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PasswordResetBegin",
                    "enter_text": {"text": user_id, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PasswordResetChooseChallenge(self, choices="0"):
        self.__flow_token_check()
        self.__method_check("PasswordResetChooseChallenge")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PasswordResetChooseChallenge",
                    "choice_selection": {
                        "link": "next_link",
                        "selected_choices": [choices],
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PwrKnowledgeChallenge(self, text):
        self.__flow_token_check()
        self.__method_check("PwrKnowledgeChallenge")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PwrKnowledgeChallenge",
                    "enter_text": {"text": text, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PasswordResetConfirmChallenge(self, code):
        self.__flow_token_check()
        self.__method_check("PasswordResetConfirmChallenge")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PasswordResetConfirmChallenge",
                    "enter_text": {"text": code, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PasswordResetNewPassword(self, password):
        self.__flow_token_check()
        self.__method_check("PasswordResetNewPassword")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PasswordResetNewPassword",
                    "enter_password": {"password": password, "link": "next_link"},
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    def PasswordResetSurvey(self, choices="0"):
        self.__flow_token_check()
        self.__method_check("PasswordResetSurvey")
        data = {
            "flow_token": self.flow_token,
            "subtask_inputs": [
                {
                    "subtask_id": "PasswordResetSurvey",
                    "choice_selection": {
                        "link": "next_link",
                        "selected_choices": [choices],
                    },
                }
            ],
        }
        response = self.session.post(
            "https://api.x.com/1.1/onboarding/task.json",
            headers=self.__get_headers(),
            json=data,
            proxies=self.proxies,
        ).json()
        self.__error_check(response)
        self.flow_token = response.get("flow_token")
        self.content = response
        return self

    # ログイン後

    def CreateTweet(self, tweet_text):
        data = {
            "queryId": "XyvN0Wv13eeu_gVIHDi10g",
            "variables": json.dumps(
                {
                    "tweet_text": tweet_text,
                    "media": {"media_entities": [], "possibly_sensitive": False},
                    "withDownvotePerspective": False,
                    "withReactionsMetadata": False,
                    "withReactionsPerspective": False,
                    "withSuperFollowsTweetFields": True,
                    "withSuperFollowsUserFields": False,
                    "semantic_annotation_ids": [],
                    "dark_request": False,
                    "withBirdwatchPivots": False,
                }
            ),
        }
        response = self.session.post(
            "https://api.x.com/graphql/XyvN0Wv13eeu_gVIHDi10g/CreateTweet",
            headers=self.__get_headers(),
            json=data,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    def FavoriteTweet(self, tweet_id):
        data = {
            "queryId": "lI07N6Otwv1PhnEgXILM7A",
            "variables": json.dumps(
                {
                    "tweet_id": tweet_id,
                }
            ),
        }
        response = self.session.post(
            "https://api.x.com/graphql/lI07N6Otwv1PhnEgXILM7A/FavoriteTweet",
            headers=self.__get_headers(),
            json=data,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    def UnfavoriteTweet(self, tweet_id):
        data = {
            "queryId": "ZYKSe-w7KEslx3JhSIk5LA",
            "variables": json.dumps(
                {
                    "tweet_id": tweet_id,
                }
            ),
        }
        response = self.session.post(
            "https://api.x.com/graphql/ZYKSe-w7KEslx3JhSIk5LA/UnfavoriteTweet",
            headers=self.__get_headers(),
            json=data,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    def CreateRetweet(self, tweet_id):
        data = {
            "queryId": "ojPdsZsimiJrUGLR1sjUtA",
            "variables": json.dumps(
                {
                    "tweet_id": tweet_id,
                    "dark_request": False,
                }
            ),
        }
        response = self.session.post(
            "https://api.x.com/graphql/ojPdsZsimiJrUGLR1sjUtA/CreateRetweet",
            headers=self.__get_headers(),
            json=data,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    def DeleteRetweet(self, tweet_id):
        data = {
            "queryId": "iQtK4dl5hBmXewYZuEOKVw",
            "variables": json.dumps(
                {
                    "source_tweet_id": tweet_id,
                    "dark_request": False,
                }
            ),
        }
        response = self.session.post(
            "https://api.x.com/graphql/iQtK4dl5hBmXewYZuEOKVw/DeleteRetweet",
            headers=self.__get_headers(),
            json=data,
        ).json()
        self.__error_check(response)
        self.content = response
        return self

    # Legacy API v1.1

    def friendships_create(self, tweet_id):
        data = {
            "include_profile_interstitial_type": 1,
            "include_blocking": 1,
            "include_blocked_by": 1,
            "include_followed_by": 1,
            "include_want_retweets": 1,
            "include_mute_edge": 1,
            "include_can_dm": 1,
            "include_can_media_tag": 1,
            "include_ext_has_nft_avatar": 1,
            "skip_status": 1,
            "id": tweet_id,
        }
        response = self.session.post(
            "https://api.x.com/1.1/friendships/create.json",
            headers=self.__get_headers_legacy(),
            data=data,
        ).json()
        self.content = response
        return self

    def friendships_destroy(self, tweet_id):
        data = {
            "include_profile_interstitial_type": 1,
            "include_blocking": 1,
            "include_blocked_by": 1,
            "include_followed_by": 1,
            "include_want_retweets": 1,
            "include_mute_edge": 1,
            "include_can_dm": 1,
            "include_can_media_tag": 1,
            "include_ext_has_nft_avatar": 1,
            "skip_status": 1,
            "id": tweet_id,
        }
        response = self.session.post(
            "https://api.x.com/1.1/friendships/destroy.json",
            headers=self.__get_headers_legacy(),
            data=data,
        ).json()
        self.content = response
        return self
