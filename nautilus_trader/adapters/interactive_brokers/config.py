# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2022 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

import os
from typing import Optional

from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig


class InteractiveBrokersDataClientConfig(LiveDataClientConfig):
    """
    Configuration for ``InteractiveBrokersDataClient`` instances.

    Parameters
    ----------
    username : str, optional
        The Interactive Brokers account username.
        If ``None`` then will source the `TWS_USERNAME`
    password : str, optional
        The Interactive Brokers account password.
        If ``None`` then will source the `TWS_PASSWORD`
    account_id : str, optional
        The account_id to use for nautilus
    gateway_host : str, optional
        The hostname for the gateway server
    gateway_port : int, optional
        The port for the gateway server
    """

    username: Optional[str] = None
    password: Optional[str] = None
    account_id: str = "001"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 4001

    def __init__(self, **kwargs):
        kwargs["username"] = kwargs.get("username", os.environ["TWS_USERNAME"])
        kwargs["password"] = kwargs.get("password", os.environ["TWS_PASSWORD"])
        super().__init__(**kwargs)


class InteractiveBrokersExecClientConfig(LiveExecClientConfig):
    """
    Configuration for ``InteractiveBrokersExecClient`` instances.

    Parameters
    ----------
    username : str, optional
        The Interactive Brokers account username.
        If ``None`` then will source the `TWS_USERNAME`
    password : str, optional
        The Interactive Brokers account password.
        If ``None`` then will source the `TWS_PASSWORD`
    account_id : str, optional
        The account_id to use for nautilus
    gateway_host : str, optional
        The hostname for the gateway server
    gateway_port : int, optional
        The port for the gateway server
    """

    username: Optional[str] = None
    password: Optional[str] = None
    account_id: str = "001"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 4001

    def __init__(self, **kwargs):
        kwargs["username"] = kwargs.get("username", os.environ["TWS_USERNAME"])
        kwargs["password"] = kwargs.get("password", os.environ["TWS_PASSWORD"])
        super().__init__(**kwargs)
