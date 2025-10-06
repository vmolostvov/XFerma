import os
import sys
import time
import traceback

import requests
# from requests_oauthlib import OAuth1

MEDIA_ENDPOINT_URL = 'https://upload.x.com/i/media/upload.json'
PFP_UPDATE_URL = 'https://api.x.com/1.1/account/update_profile_image.json'

FILENAME = 'test_logo.jpg'


class TwitterMedia(object):

    def __init__(self, file_name, headers, proxies):
        '''
        Defines media properties
        '''
        self.media_filename = file_name
        self.headers = headers
        self.proxies = proxies
        self.total_bytes = os.path.getsize(self.media_filename)
        self.media_id = None
        self.processing_info = None

        self.headers.pop('content-type')

    def upload_init(self):
        '''
        Initializes Upload
        '''
        print('INIT')

        request_data = {
            'command': 'INIT',
            'media_type': 'image/jpeg',
            'total_bytes': self.total_bytes,
            'enable_1080p_variant': True,
            # 'media_category': self.media_category,
            # 'shared': True  # for media reuse in DMs. See: https://dev.twitter.com/rest/direct-messages/attaching-media
        }

        req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, headers=self.headers, proxies=self.proxies)
        media_id = req.json()['media_id']

        self.media_id = media_id

        print('Media ID: %s' % str(media_id))

    def upload_append(self):
        '''
        Uploads media in chunks and appends to chunks uploaded
        '''
        segment_id = 0
        bytes_sent = 0
        file = open(self.media_filename, 'rb')

        while bytes_sent < self.total_bytes:
            chunk = file.read(4 * 1024 * 1024)

            print('APPEND')

            request_data = {
                'command': 'APPEND',
                'media_id': self.media_id,
                'segment_index': segment_id
            }

            files = {
                'media': chunk
            }

            req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, files=files, headers=self.headers, proxies=self.proxies)

            if req.status_code < 200 or req.status_code > 299:
                print(req.status_code)
                print(req.text)
                sys.exit(0)

            segment_id = segment_id + 1
            bytes_sent = file.tell()

            print('%s of %s bytes uploaded' % (str(bytes_sent), str(self.total_bytes)))

        print('Upload chunks complete')

    def upload_finalize(self):
        '''
        Finalizes uploads and starts video processing
        '''
        print('FINALIZE')

        request_data = {
            'command': 'FINALIZE',
            'media_id': self.media_id
        }

        req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, headers=self.headers, proxies=self.proxies)

        self.processing_info = req.json().get('processing_info', None)
        self.check_status()

    def check_status(self):
        '''
        Checks video processing status
        '''
        if self.processing_info is None:
            return

        state = self.processing_info['state']

        print('Media processing status is %s ' % state)

        if state == u'succeeded':
            return

        if state == u'failed':
            sys.exit(0)

        check_after_secs = self.processing_info['check_after_secs']

        print('Checking after %s seconds' % str(check_after_secs))
        time.sleep(check_after_secs)

        print('STATUS')

        request_params = {
            'command': 'STATUS',
            'media_id': self.media_id
        }

        req = requests.get(url=MEDIA_ENDPOINT_URL, params=request_params, headers=self.headers, proxies=self.proxies)

        self.processing_info = req.json().get('processing_info', None)
        self.check_status()

    def update_pfp(self):

        params = {
            "include_profile_interstitial_type": 1,
            "include_blocking": 1,
            "include_blocked_by": 1,
            "include_followed_by": 1,
            "include_want_retweets": 1,
            "include_mute_edge": 1,
            "include_can_dm": 1,
            "include_can_media_tag": 1,
            "include_ext_is_blue_verified": 1,
            "include_ext_verified_type": 1,
            "include_ext_profile_image_shape": 1,
            "skip_status": 1,
            "return_user": True,
            "media_id": self.media_id
        }

        req = requests.post(url=PFP_UPDATE_URL, params=params, headers=self.headers, proxies=self.proxies)
        return req.json()


def upload_and_update_pfp(filename, headers, proxies):
    try:
        twitterMedia = TwitterMedia(filename, headers, proxies)
        twitterMedia.upload_init()
        twitterMedia.upload_append()
        twitterMedia.upload_finalize()
        update_pfp_res = twitterMedia.update_pfp()
        if not update_pfp_res["default_profile_image"]:
            return True
        return False
    except:
        print(traceback.format_exc())


# if __name__ == '__main__':
#     import twitter_search
#     twitter_search.load_accounts_cookies_login()
#     twitter_working_account = twitter_search.twitter_working_accounts[0]
#     twitter_cookies_dict = twitter_working_account["cookies_dict"]
#     headers = twitter_search.get_headers_for_twitter_account(twitter_cookies_dict)
#     proxies = twitter_search.get_proxies_for_twitter_account(twitter_working_account)
#     twitterMedia = TwitterMedia(FILENAME, headers, proxies)
#     twitterMedia.upload_init()
#     twitterMedia.upload_append()
#     twitterMedia.upload_finalize()
#     twitterMedia.update_pfp()