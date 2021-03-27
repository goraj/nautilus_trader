# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2021 Nautech Systems Pty Ltd. All rights reserved.
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


cpdef enum ComponentState:
    INITIALIZED = 1,
    STARTING = 2,
    RUNNING = 3,
    STOPPING = 4,
    STOPPED = 5,
    RESUMING = 6,
    RESETTING = 7,
    DISPOSING = 8,
    DISPOSED = 9,
    FAULTED = 10,


cdef class ComponentStateParser:

    @staticmethod
    cdef str to_str(int value)

    @staticmethod
    cdef ComponentState from_str(str value) except *
