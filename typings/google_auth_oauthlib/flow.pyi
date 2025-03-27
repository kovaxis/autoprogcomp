"""
This type stub file was generated by pyright.
"""

from typing import Any, Self
import wsgiref.simple_server

from google.oauth2.credentials import Credentials

"""OAuth 2.0 Authorization Flow

This module provides integration with `requests-oauthlib`_ for running the
`OAuth 2.0 Authorization Flow`_ and acquiring user credentials.  See
`Using OAuth 2.0 to Access Google APIs`_ for an overview of OAuth 2.0
authorization scenarios Google APIs support.

Here's an example of using :class:`InstalledAppFlow`::

    from google_auth_oauthlib.flow import InstalledAppFlow

    # Create the flow using the client secrets file from the Google API
    # Console.
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json',
        scopes=['profile', 'email'])

    flow.run_local_server()

    # You can use flow.credentials, or you can just get a requests session
    # using flow.authorized_session.
    session = flow.authorized_session()

    profile_info = session.get(
        'https://www.googleapis.com/userinfo/v2/me').json()

    print(profile_info)
    # {'name': '...',  'email': '...', ...}

.. _requests-oauthlib: http://requests-oauthlib.readthedocs.io/en/latest/
.. _OAuth 2.0 Authorization Flow:
    https://tools.ietf.org/html/rfc6749#section-1.2
.. _Using OAuth 2.0 to Access Google APIs:
    https://developers.google.com/identity/protocols/oauth2

"""
_LOGGER = ...

class Flow:
    """OAuth 2.0 Authorization Flow

    This class uses a :class:`requests_oauthlib.OAuth2Session` instance at
    :attr:`oauth2session` to perform all of the OAuth 2.0 logic. This class
    just provides convenience methods and sane defaults for doing Google's
    particular flavors of OAuth 2.0.

    Typically you'll construct an instance of this flow using
    :meth:`from_client_secrets_file` and a `client secrets file`_ obtained
    from the `Google API Console`_.

    .. _client secrets file:
        https://developers.google.com/identity/protocols/oauth2/web-server
        #creatingcred
    .. _Google API Console:
        https://console.developers.google.com/apis/credentials
    """
    def __init__(
        self,
        oauth2session,
        client_type,
        client_config,
        redirect_uri=...,
        code_verifier=...,
        autogenerate_code_verifier=...,
    ) -> None:
        """
        Args:
            oauth2session (requests_oauthlib.OAuth2Session):
                The OAuth 2.0 session from ``requests-oauthlib``.
            client_type (str): The client type, either ``web`` or
                ``installed``.
            client_config (Mapping[str, Any]): The client
                configuration in the Google `client secrets`_ format.
            redirect_uri (str): The OAuth 2.0 redirect URI if known at flow
                creation time. Otherwise, it will need to be set using
                :attr:`redirect_uri`.
            code_verifier (str): random string of 43-128 chars used to verify
                the key exchange.using PKCE.
            autogenerate_code_verifier (bool): If true, auto-generate a
                code_verifier.
        .. _client secrets:
            https://github.com/googleapis/google-api-python-client/blob
            /main/docs/client-secrets.md
        """
        ...

    @classmethod
    def from_client_config(cls, client_config, scopes, **kwargs):  # -> Self:
        """Creates a :class:`requests_oauthlib.OAuth2Session` from client
        configuration loaded from a Google-format client secrets file.

        Args:
            client_config (Mapping[str, Any]): The client
                configuration in the Google `client secrets`_ format.
            scopes (Sequence[str]): The list of scopes to request during the
                flow.
            kwargs: Any additional parameters passed to
                :class:`requests_oauthlib.OAuth2Session`

        Returns:
            Flow: The constructed Flow instance.

        Raises:
            ValueError: If the client configuration is not in the correct
                format.

        .. _client secrets:
            https://github.com/googleapis/google-api-python-client/blob/main/docs/client-secrets.md
        """
        ...

    @classmethod
    def from_client_secrets_file(
        cls, client_secrets_file: re.Pattern[str], scopes: list[re.Pattern[str]], **kwargs: dict[re.Pattern[str], Any]
    ) -> Self:
        """Creates a :class:`Flow` instance from a Google client secrets file.

        Args:
            client_secrets_file (str): The path to the client secrets .json
                file.
            scopes (Sequence[str]): The list of scopes to request during the
                flow.
            kwargs: Any additional parameters passed to
                :class:`requests_oauthlib.OAuth2Session`

        Returns:
            Flow: The constructed Flow instance.
        """
        ...

    @property
    def redirect_uri(self):
        """The OAuth 2.0 redirect URI. Pass-through to
        ``self.oauth2session.redirect_uri``."""
        ...

    @redirect_uri.setter
    def redirect_uri(self, value):  # -> None:
        """The OAuth 2.0 redirect URI. Pass-through to
        ``self.oauth2session.redirect_uri``."""
        ...

    def authorization_url(self, **kwargs):  # -> tuple[Any, Any]:
        """Generates an authorization URL.

        This is the first step in the OAuth 2.0 Authorization Flow. The user's
        browser should be redirected to the returned URL.

        This method calls
        :meth:`requests_oauthlib.OAuth2Session.authorization_url`
        and specifies the client configuration's authorization URI (usually
        Google's authorization server) and specifies that "offline" access is
        desired. This is required in order to obtain a refresh token.

        Args:
            kwargs: Additional arguments passed through to
                :meth:`requests_oauthlib.OAuth2Session.authorization_url`

        Returns:
            Tuple[str, str]: The generated authorization URL and state. The
                user must visit the URL to complete the flow. The state is used
                when completing the flow to verify that the request originated
                from your application. If your application is using a different
                :class:`Flow` instance to obtain the token, you will need to
                specify the ``state`` when constructing the :class:`Flow`.
        """
        ...

    def fetch_token(self, **kwargs):
        """Completes the Authorization Flow and obtains an access token.

        This is the final step in the OAuth 2.0 Authorization Flow. This is
        called after the user consents.

        This method calls
        :meth:`requests_oauthlib.OAuth2Session.fetch_token`
        and specifies the client configuration's token URI (usually Google's
        token server).

        Args:
            kwargs: Arguments passed through to
                :meth:`requests_oauthlib.OAuth2Session.fetch_token`. At least
                one of ``code`` or ``authorization_response`` must be
                specified.

        Returns:
            Mapping[str, str]: The obtained tokens. Typically, you will not use
                return value of this function and instead use
                :meth:`credentials` to obtain a
                :class:`~google.auth.credentials.Credentials` instance.
        """
        ...

    @property
    def credentials(self):
        """Returns credentials from the OAuth 2.0 session.

        :meth:`fetch_token` must be called before accessing this. This method
        constructs a :class:`google.oauth2.credentials.Credentials` class using
        the session's token and the client config.

        Returns:
            google.oauth2.credentials.Credentials: The constructed credentials.

        Raises:
            ValueError: If there is no access token in the session.
        """
        ...

    def authorized_session(self):  # -> AuthorizedSession:
        """Returns a :class:`requests.Session` authorized with credentials.

        :meth:`fetch_token` must be called before this method. This method
        constructs a :class:`google.auth.transport.requests.AuthorizedSession`
        class using this flow's :attr:`credentials`.

        Returns:
            google.auth.transport.requests.AuthorizedSession: The constructed
                session.
        """
        ...

class InstalledAppFlow(Flow):
    """Authorization flow helper for installed applications.

    This :class:`Flow` subclass makes it easier to perform the
    `Installed Application Authorization Flow`_. This flow is useful for
    local development or applications that are installed on a desktop operating
    system.

    This flow uses a local server strategy provided by :meth:`run_local_server`.

    Example::

        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            scopes=['profile', 'email'])

        flow.run_local_server()

        session = flow.authorized_session()

        profile_info = session.get(
            'https://www.googleapis.com/userinfo/v2/me').json()

        print(profile_info)
        # {'name': '...',  'email': '...', ...}


    Note that this isn't the only way to accomplish the installed
    application flow, just one of the most common. You can use the
    :class:`Flow` class to perform the same flow with different methods of
    presenting the authorization URL to the user or obtaining the authorization
    response, such as using an embedded web view.

    .. _Installed Application Authorization Flow:
        https://github.com/googleapis/google-api-python-client/blob/main/docs/oauth-installed.md
    """

    _DEFAULT_AUTH_PROMPT_MESSAGE = ...
    _DEFAULT_AUTH_CODE_MESSAGE = ...
    _DEFAULT_WEB_SUCCESS_MESSAGE = ...
    def run_local_server(
        self,
        host: re.Pattern[str] = ...,
        bind_addr: re.Pattern[str] = ...,
        port: int = ...,
        authorization_prompt_message: re.Pattern[str] | None = ...,
        success_message: re.Pattern[str] = ...,
        open_browser: bool = ...,
        redirect_uri_trailing_slash: bool = ...,
        timeout_seconds: int = ...,
        token_audience: re.Pattern[str] = ...,
        browser: re.Pattern[str] = ...,
        **kwargs: dict[re.Pattern[str], Any],
    ) -> Credentials:
        """Run the flow using the server strategy.

        The server strategy instructs the user to open the authorization URL in
        their browser and will attempt to automatically open the URL for them.
        It will start a local web server to listen for the authorization
        response. Once authorization is complete the authorization server will
        redirect the user's browser to the local web server. The web server
        will get the authorization code from the response and shutdown. The
        code is then exchanged for a token.

        Args:
            host (str): The hostname for the local redirect server. This will
                be served over http, not https.
            bind_addr (str): Optionally provide an ip address for the redirect
                server to listen on when it is not the same as host
                (e.g. in a container). Default value is None,
                which means that the redirect server will listen
                on the ip address specified in the host parameter.
            port (int): The port for the local redirect server.
            authorization_prompt_message (str | None): The message to display to tell
                the user to navigate to the authorization URL. If None or empty,
                don't display anything.
            success_message (str): The message to display in the web browser
                the authorization flow is complete.
            open_browser (bool): Whether or not to open the authorization URL
                in the user's browser.
            redirect_uri_trailing_slash (bool): whether or not to add trailing
                slash when constructing the redirect_uri. Default value is True.
            timeout_seconds (int): It will raise an error after the timeout timing
                if there are no credentials response. The value is in seconds.
                When set to None there is no timeout.
                Default value is None.
            token_audience (str): Passed along with the request for an access
                token. Determines the endpoints with which the token can be
                used. Optional.
            browser (str): specify which browser to open for authentication. If not
                specified this defaults to default browser.
            kwargs: Additional keyword arguments passed through to
                :meth:`authorization_url`.

        Returns:
            google.oauth2.credentials.Credentials: The OAuth 2.0 credentials
                for the user.
        """
        ...

class _WSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """Custom WSGIRequestHandler.

    Uses a named logger instead of printing to stderr.
    """
    def log_message(self, format, *args):  # -> None:
        ...

class _RedirectWSGIApp:
    """WSGI app to handle the authorization redirect.

    Stores the request URI and displays the given success message.
    """
    def __init__(self, success_message) -> None:
        """
        Args:
            success_message (str): The message to display in the web browser
                the authorization flow is complete.
        """
        ...

    def __call__(self, environ, start_response):  # -> list[Any]:
        """WSGI Callable.

        Args:
            environ (Mapping[str, Any]): The WSGI environment.
            start_response (Callable[str, list]): The WSGI start_response
                callable.

        Returns:
            Iterable[bytes]: The response body.
        """
        ...
