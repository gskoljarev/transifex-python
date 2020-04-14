import logging
import sys

import requests
from transifex.native.consts import (KEY_CHARACTER_LIMIT,
                                     KEY_DEVELOPER_COMMENT, KEY_TAGS)

TRANSIFEX_CDS_HOST = 'https://cds.svc.transifex.net'

TRANSIFEX_CDS_URLS = {
    'FETCH_AVAILABLE_LANGUAGES': '/languages',
    'FETCH_TRANSLATIONS_FOR_LANGUAGE': '/content/{language_code}',
    'PUSH_SOURCE_STRINGS': '/content/'
}

logger = logging.getLogger('transifex.native.cds')
logger.addHandler(logging.StreamHandler(sys.stderr))


# A mapping of meta keys
# (interface_key: cds_key)
# Only contains meta keys that are different between the two
MAPPING = {
    KEY_DEVELOPER_COMMENT: 'developer_comment',
    KEY_CHARACTER_LIMIT: 'character_limit',
    KEY_TAGS: 'tags',
}


class CDSHandler(object):
    """Handles communication with the Content Delivery Service."""

    def __init__(self, configured_languages, token, secret=None, host=TRANSIFEX_CDS_HOST):
        """Constructor.

        :param list configured_languages: a list of language codes for the
            configured languages in the application
        :param str token: the API token to use for connecting to the CDS
        :param str host: the host of the Content Delivery Service
        """
        self.configured_language_codes = configured_languages
        self.token = token
        self.secret = secret
        self.host = host or TRANSIFEX_CDS_HOST

    def fetch_languages(self):
        """Fetch the languages defined in the CDS for the specific project.

        :return: a list of language information
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_AVAILABLE_LANGUAGES']
        languages = []

        try:
            response = requests.get(
                self.host + cds_url,
                headers={"Authorization": "Bearer {token}".format(
                    token=self.token)}
            )

            if not response.ok:
                logger.error(
                    'Error retrieving languages from CDS: `{}`'.format(
                        response.reason
                    )
                )
                response.raise_for_status()

            json_content = response.json()
            languages = json_content['data']

        except (KeyError, ValueError):
            # Compatibility with python2.7 where `JSONDecodeError` doesn't exist
            logger.error(
                'Error retrieving languages from CDS: Malformed response')
        except requests.ConnectionError:
            logger.error(
                'Error retrieving languages from CDS: ConnectionError')
        except Exception as e:
            logger.error(
                'Error retrieving languages from CDS: UnknownError (`{}`)'.format(
                    str(e)
                )
            )

        return languages

    def fetch_translations(self, language_code=None):
        """Fetch all translations for the given organization/project/(resource)
        associated with the current token.

        :return: a dictionary with all corresponding translations
        :rtype: dict
        """

        cds_url = TRANSIFEX_CDS_URLS['FETCH_TRANSLATIONS_FOR_LANGUAGE']

        translations = {}

        try:

            if not language_code:
                languages = [lang['code'] for lang in self.fetch_languages()]
            else:
                languages = [language_code]

            for language_code in set(languages) & \
                    set(self.configured_language_codes):
                response = requests.get(
                    self.host + cds_url.format(language_code=language_code),
                    headers={"Authorization": "Bearer {token}".format(
                        token=self.token)}
                )

                if not response.ok:
                    logger.error(
                        'Error retrieving translations from CDS: `{}`'.format(
                            response.reason
                        )
                    )
                    response.raise_for_status()

                json_content = response.json()
                translations[language_code] = json_content['data']

        except (KeyError, ValueError):
            # Compatibility with python2.7 where `JSONDecodeError` doesn't exist
            logger.error(
                'Error retrieving translations from CDS: Malformed response')
        except requests.ConnectionError:
            logger.error(
                'Error retrieving translations from CDS: ConnectionError')
        except Exception as e:
            logger.error(
                'Error retrieving translations from CDS: UnknownError (`{}`)'.format(
                    str(e)
                )
            )

        return translations

    def push_source_strings(self, strings, purge=False):
        """Push source strings to CDS.

        :param list(SourceString) strings: a list of `SourceString` objects holding
            source strings
        :param bool purge: True deletes destination source content not included in
                           pushed content.
                           False appends the pushed content to destination source
                           content.
        :return: the HTTP response object
        :rtype: requests.Response
        """
        if not self.secret:
            raise Exception(
                'You need to use `TRANSIFEX_SECRET` when pushing source content'
            )

        cds_url = TRANSIFEX_CDS_URLS['PUSH_SOURCE_STRINGS']

        data = {k: v for k, v in [self._serialize(item) for item in strings]}
        try:
            response = requests.post(
                self.host + cds_url,
                headers={"Authorization": "Bearer {token}:{secret}".format(
                    token=self.token, secret=self.secret)
                },
                json={
                    'data': data,
                    'meta': {'purge': purge},
                }
            )
            response.raise_for_status()

        except requests.ConnectionError:
            logger.error(
                'Error pushing source strings to CDS: ConnectionError')
        except Exception as e:
            logger.error(
                'Error pushing source strings to CDS: UnknownError (`{}`)'.format(
                    str(e)
                )
            )

        return response

    def _serialize(self, source_string):
        """Serialize the given source string to a format suitable for the CDS.

        :param transifex.native.parsing.SourceString source_string: the object
            to serialize
        :return: a tuple that contains ths string key and its data,
            as (key, data)
        :rtype: tuple
        """
        data = {
            'string': source_string.string,
            'meta': {
                MAPPING.get(k, k): v
                for k, v in source_string.meta.items()
            },
        }
        if source_string.context:
            data['meta']['context'] = source_string.context

        return source_string.key, data