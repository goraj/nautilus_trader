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

import asyncio
import pickle
import sys

import fsspec
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pytest

from nautilus_trader.adapters.betfair.providers import BetfairInstrumentProvider
from nautilus_trader.adapters.betfair.util import make_betfair_reader
from nautilus_trader.backtest.data.providers import TestInstrumentProvider
from nautilus_trader.model.data.tick import QuoteTick
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.persistence.catalog import DataCatalog
from nautilus_trader.persistence.external.core import RawFile
from nautilus_trader.persistence.external.core import _validate_dataset
from nautilus_trader.persistence.external.core import dicts_to_dataframes
from nautilus_trader.persistence.external.core import process_files
from nautilus_trader.persistence.external.core import process_raw_file
from nautilus_trader.persistence.external.core import scan_files
from nautilus_trader.persistence.external.core import split_and_serialize
from nautilus_trader.persistence.external.core import validate_data_catalog
from nautilus_trader.persistence.external.core import write_objects
from nautilus_trader.persistence.external.core import write_parquet
from nautilus_trader.persistence.external.core import write_tables
from nautilus_trader.persistence.external.readers import CSVReader
from tests.integration_tests.adapters.betfair.test_kit import BetfairTestStubs
from tests.test_kit import PACKAGE_ROOT
from tests.test_kit.mocks.data import MockReader
from tests.test_kit.mocks.data import NewsEventData
from tests.test_kit.mocks.data import data_catalog_setup
from tests.test_kit.stubs.identifiers import TestIdStubs
from tests.test_kit.stubs.persistence import TestPersistenceStubs
from tests.unit_tests.backtest.test_backtest_config import TEST_DATA_DIR


TEST_DATA = PACKAGE_ROOT + "/data"


@pytest.mark.skipif(sys.platform == "win32", reason="test path broken on windows")
class TestPersistenceCore:
    def setup(self):
        data_catalog_setup()
        self.catalog = DataCatalog.from_env()
        self.fs = self.catalog.fs
        self.reader = MockReader()

    def _loaded_data_into_catalog(self):
        self.instrument_provider = BetfairInstrumentProvider.from_instruments([])
        result = process_files(
            glob_path=PACKAGE_ROOT + "/data/1.166564490*.bz2",
            reader=BetfairTestStubs.betfair_reader(instrument_provider=self.instrument_provider),
            instrument_provider=self.instrument_provider,
            catalog=self.catalog,
        )
        assert result
        data = (
            self.catalog.instruments(as_nautilus=True)
            + self.catalog.instrument_status_updates(as_nautilus=True)
            + self.catalog.trade_ticks(as_nautilus=True)
            + self.catalog.order_book_deltas(as_nautilus=True)
            + self.catalog.tickers(as_nautilus=True)
        )
        return data

    def test_raw_file_block_size_read(self):
        # Arrange
        raw_file = RawFile(fsspec.open(f"{TEST_DATA}/1.166564490.bz2"))
        data = b"".join(raw_file.iter())

        # Act
        raw_file = RawFile(
            fsspec.open(f"{TEST_DATA}/1.166564490.bz2"),
            block_size=1000,
        )
        blocks = list(raw_file.iter())

        # Assert
        assert len(blocks) == 18
        assert b"".join(blocks) == data
        assert len(data) == 17338

    def test_raw_file_process(self):
        # Arrange
        rf = RawFile(
            open_file=fsspec.open(f"{TEST_DATA}/1.166564490.bz2", compression="infer"),
            block_size=None,
        )

        # Act
        process_raw_file(catalog=self.catalog, reader=make_betfair_reader(), raw_file=rf)

        # Assert
        assert len(self.catalog.instruments()) == 2

    def test_raw_file_pickleable(self):
        # Arrange
        path = TEST_DATA_DIR + "/betfair/1.166811431.bz2"  # total size = 151707
        expected = RawFile(open_file=fsspec.open(path, compression="infer"))

        # Act
        data = pickle.dumps(expected)
        result: RawFile = pickle.loads(data)  # noqa: S301

        # Assert
        assert result.open_file.fs == expected.open_file.fs
        assert result.open_file.path == expected.open_file.path
        assert result.block_size == expected.block_size
        assert result.open_file.compression == "bz2"

    @pytest.mark.parametrize(
        "glob, num_files",
        [
            ("**.json", 4),
            ("**.txt", 3),
            ("**.parquet", 2),
            ("**.csv", 15),
        ],
    )
    def test_scan_paths(self, glob, num_files):
        files = scan_files(glob_path=f"{TEST_DATA_DIR}/{glob}")
        assert len(files) == num_files

    def test_scan_file_filter(
        self,
    ):
        files = scan_files(glob_path=f"{TEST_DATA_DIR}/*.csv")
        assert len(files) == 15

        files = scan_files(glob_path=f"{TEST_DATA_DIR}/*jpy*.csv")
        assert len(files) == 3

    def test_nautilus_chunk_to_dataframes(self):
        # Arrange, Act
        data = self._loaded_data_into_catalog()
        dfs = split_and_serialize(data)
        result = {}
        for cls in dfs:
            for ins in dfs[cls]:
                result[cls.__name__] = len(dfs[cls][ins])

        # Assert
        assert result == {
            "BetfairTicker": 82,
            "BettingInstrument": 2,
            "InstrumentStatusUpdate": 1,
            "OrderBookData": 1077,
            "TradeTick": 114,
        }

    def test_write_parquet_no_partitions(
        self,
    ):
        # Arrange
        df = pd.DataFrame(
            {"value": np.random.random(5), "instrument_id": ["a", "a", "a", "b", "b"]}
        )
        catalog = DataCatalog.from_env()
        fs = catalog.fs
        root = catalog.path

        # Act
        write_parquet(
            fs=fs,
            path=f"{root}/sample.parquet",
            df=df,
            schema=pa.schema({"value": pa.float64(), "instrument_id": pa.string()}),
            partition_cols=None,
        )
        result = (
            ds.dataset(str(root.joinpath("sample.parquet")), filesystem=fs).to_table().to_pandas()
        )

        # Assert
        assert result.equals(df)

    def test_write_parquet_partitions(
        self,
    ):
        # Arrange
        catalog = DataCatalog.from_env()
        fs = catalog.fs
        root = catalog.path
        path = "sample.parquet"

        df = pd.DataFrame(
            {"value": np.random.random(5), "instrument_id": ["a", "a", "a", "b", "b"]}
        )

        # Act
        write_parquet(
            fs=fs,
            path=f"{root}/{path}",
            df=df,
            schema=pa.schema({"value": pa.float64(), "instrument_id": pa.string()}),
            partition_cols=["instrument_id"],
        )
        dataset = ds.dataset(str(root.joinpath("sample.parquet")), filesystem=fs)
        result = dataset.to_table().to_pandas()

        # Assert
        assert result.equals(df[["value"]])  # instrument_id is a partition now
        assert dataset.files[0].startswith("/.nautilus/catalog/sample.parquet/instrument_id=a/")
        assert dataset.files[1].startswith("/.nautilus/catalog/sample.parquet/instrument_id=b/")

    def test_write_parquet_determine_partitions_writes_instrument_id(
        self,
    ):
        # Arrange
        quote = QuoteTick(
            instrument_id=TestIdStubs.audusd_id(),
            bid=Price.from_str("0.80"),
            ask=Price.from_str("0.81"),
            bid_size=Quantity.from_int(1000),
            ask_size=Quantity.from_int(1000),
            ts_event=0,
            ts_init=0,
        )
        chunk = [quote]
        tables = dicts_to_dataframes(split_and_serialize(chunk))

        # Act
        write_tables(catalog=self.catalog, tables=tables)

        # Assert
        files = self.fs.ls(f"{self.catalog.path}/data/quote_tick.parquet")
        expected = f"{self.catalog.path}/data/quote_tick.parquet/instrument_id=AUD-USD.SIM"
        assert expected in files

    @pytest.mark.asyncio
    async def test_load_text_betfair(self):
        # Arrange
        instrument_provider = BetfairInstrumentProvider.from_instruments([])

        # Act
        files = process_files(
            glob_path=f"{TEST_DATA_DIR}/**.bz2",
            reader=BetfairTestStubs.betfair_reader(instrument_provider=instrument_provider),
            catalog=self.catalog,
            instrument_provider=instrument_provider,
        )

        await asyncio.sleep(2)  # Allow `ThreadPoolExecutor` to complete processing

        # Assert
        assert files == {
            TEST_DATA_DIR + "/1.166564490.bz2": 2908,
            TEST_DATA_DIR + "/betfair/1.180305278.bz2": 17085,
            TEST_DATA_DIR + "/betfair/1.166811431.bz2": 22692,
        }

    def test_data_catalog_instruments_no_partition(self):
        # Arrange, Act
        self._loaded_data_into_catalog()
        path = f"{self.catalog.path}/data/betting_instrument.parquet"
        dataset = pq.ParquetDataset(
            path_or_paths=path,
            filesystem=self.fs,
        )
        partitions = dataset.partitions

        # Assert
        assert not partitions.levels

    def test_data_catalog_metadata(self):
        # Arrange, Act, Assert
        self._loaded_data_into_catalog()
        assert ds.parquet_dataset(
            f"{self.catalog.path}/data/trade_tick.parquet/_common_metadata",
            filesystem=self.fs,
        )

    def test_data_catalog_dataset_types(self):
        # Arrange
        self._loaded_data_into_catalog()

        # Act
        dataset = ds.dataset(
            str(self.catalog.path / "data" / "trade_tick.parquet"),
            filesystem=self.catalog.fs,
        )
        schema = {
            n: t.__class__.__name__ for n, t in zip(dataset.schema.names, dataset.schema.types)
        }

        # Assert
        assert schema == {
            "price": "DataType",
            "size": "DataType",
            "aggressor_side": "DictionaryType",
            "trade_id": "DataType",
            "ts_event": "DataType",
            "ts_init": "DataType",
        }

    def test_data_catalog_instruments_load(self):
        # Arrange
        instruments = [
            TestInstrumentProvider.aapl_equity(),
            TestInstrumentProvider.es_future(),
            TestInstrumentProvider.aapl_option(),
        ]
        write_objects(catalog=self.catalog, chunk=instruments)

        # Act
        instruments = self.catalog.instruments(as_nautilus=True)

        # Assert
        assert len(instruments) == 3

    def test_data_catalog_instruments_filter_by_instrument_id(self):
        # Arrange
        instruments = [
            TestInstrumentProvider.aapl_equity(),
            TestInstrumentProvider.es_future(),
            TestInstrumentProvider.aapl_option(),
        ]
        write_objects(catalog=self.catalog, chunk=instruments)

        # Act
        instrument_ids = [instrument.id.value for instrument in instruments]
        instruments = self.catalog.instruments(instrument_ids=instrument_ids)

        # Assert
        assert len(instruments) == 3

    def test_repartition_dataset(self):
        # Arrange
        catalog = DataCatalog.from_env()
        fs = catalog.fs
        root = catalog.path
        path = "sample.parquet"

        # Write some out of order, overlapping
        for start_date in ("2020-01-01", "2020-01-8", "2020-01-04"):
            df = pd.DataFrame(
                {
                    "value": np.arange(5),
                    "instrument_id": ["a", "a", "a", "b", "b"],
                    "ts_init": [
                        int(ts.to_datetime64())
                        for ts in pd.date_range(start_date, periods=5, tz="UTC")
                    ],
                }
            )
            write_parquet(
                fs=fs,
                path=f"{root}/{path}",
                df=df,
                schema=pa.schema(
                    {"value": pa.float64(), "instrument_id": pa.string(), "ts_init": pa.int64()}
                ),
                partition_cols=["instrument_id"],
            )

        original_partitions = fs.glob(f"{root}/{path}/**/*.parquet")

        # Act
        _validate_dataset(catalog=catalog, path=f"{root}/{path}")
        new_partitions = fs.glob(f"{root}/{path}/**/*.parquet")

        # Assert
        assert len(original_partitions) == 6
        expected = [
            "/.nautilus/catalog/sample.parquet/instrument_id=a/20200101.parquet",
            "/.nautilus/catalog/sample.parquet/instrument_id=a/20200104.parquet",
            "/.nautilus/catalog/sample.parquet/instrument_id=a/20200108.parquet",
            "/.nautilus/catalog/sample.parquet/instrument_id=b/20200101.parquet",
            "/.nautilus/catalog/sample.parquet/instrument_id=b/20200104.parquet",
            "/.nautilus/catalog/sample.parquet/instrument_id=b/20200108.parquet",
        ]
        assert new_partitions == expected

    def test_validate_data_catalog(self):
        # Arrange
        self._loaded_data_into_catalog()

        # Act
        validate_data_catalog(catalog=self.catalog)

        # Assert
        new_partitions = [
            f for f in self.fs.glob(f"{self.catalog.path}/**/*.parquet") if self.fs.isfile(f)
        ]
        ins1, ins2 = self.catalog.instruments()["id"].tolist()

        today_str = pd.Timestamp.utcnow().strftime("%Y%m%d")
        expected = [
            f"/.nautilus/catalog/data/betfair_ticker.parquet/instrument_id={ins1}/20191220.parquet",
            f"/.nautilus/catalog/data/betfair_ticker.parquet/instrument_id={ins2}/20191220.parquet",
            f"/.nautilus/catalog/data/betting_instrument.parquet/{today_str}.parquet",
            f"/.nautilus/catalog/data/instrument_status_update.parquet/instrument_id={ins1}/20191220.parquet",
            f"/.nautilus/catalog/data/instrument_status_update.parquet/instrument_id={ins2}/20191220.parquet",
            f"/.nautilus/catalog/data/order_book_data.parquet/instrument_id={ins1}/20191220.parquet",
            f"/.nautilus/catalog/data/order_book_data.parquet/instrument_id={ins2}/20191220.parquet",
            f"/.nautilus/catalog/data/trade_tick.parquet/instrument_id={ins1}/20191220.parquet",
            f"/.nautilus/catalog/data/trade_tick.parquet/instrument_id={ins2}/20191220.parquet",
        ]
        assert new_partitions == expected

    def test_split_and_serialize_generic_data_gets_correct_class(self):
        # Arrange
        TestPersistenceStubs.setup_news_event_persistence()
        process_files(
            glob_path=f"{TEST_DATA_DIR}/news_events.csv",
            reader=CSVReader(block_parser=TestPersistenceStubs.news_event_parser),
            catalog=self.catalog,
        )
        objs = self.catalog.generic_data(
            cls=NewsEventData, filter_expr=ds.field("currency") == "USD", as_nautilus=True
        )

        # Act
        split = split_and_serialize(objs)

        # Assert
        assert NewsEventData in split
        assert None in split[NewsEventData]
        assert len(split[NewsEventData][None]) == 22941

    def test_catalog_generic_data_not_overwritten(self):
        # Arrange
        TestPersistenceStubs.setup_news_event_persistence()
        process_files(
            glob_path=f"{TEST_DATA_DIR}/news_events.csv",
            reader=CSVReader(block_parser=TestPersistenceStubs.news_event_parser),
            catalog=self.catalog,
        )
        objs = self.catalog.generic_data(
            cls=NewsEventData, filter_expr=ds.field("currency") == "USD", as_nautilus=True
        )

        # Clear the catalog again
        data_catalog_setup()
        self.catalog = DataCatalog.from_env()

        assert (
            len(self.catalog.generic_data(NewsEventData, raise_on_empty=False, as_nautilus=True))
            == 0
        )

        chunk1, chunk2 = objs[:10], objs[5:15]

        # Act, Assert
        write_objects(catalog=self.catalog, chunk=chunk1)
        assert len(self.catalog.generic_data(NewsEventData)) == 10

        write_objects(catalog=self.catalog, chunk=chunk2)
        assert len(self.catalog.generic_data(NewsEventData)) == 15
