import unittest

import cdp

from cdp_client_multi import rows_from_packet


class RecorderRowsTests(unittest.TestCase):
    def packet(self, serial, items):
        packet = cdp.CDP(serial_number=serial)
        packet.sequence = 42
        packet.add_data_items(items)
        return cdp.CDP(packet.encode())

    def test_position_and_multiple_imu_items_keep_their_own_timestamps(self):
        packet = self.packet("01:00:05CD", [
            cdp.PositionV1(x=-120, y=210, z=900, quality=0,
                           smoothing=3, sequence=7, gnt=100),
            cdp.MPUAccelerometerV2(x=100, y=-200, z=300, gnt=101,
                                   scale=2, dlpf=41),
            cdp.MPUGyroscopeV2(x=-4, y=5, z=6, gnt=102,
                               scale=2000, dlpf=5),
            cdp.MPUAccelerometerV2(x=1, y=2, z=3, gnt=103,
                                   scale=2, dlpf=41),
        ])
        rows = list(rows_from_packet(packet, "2026-10-20T12:00:00+00:00"))
        self.assertEqual([row["item_type"] for row in rows],
                         ["position", "accelerometer", "gyroscope", "accelerometer"])
        self.assertEqual([row["network_time_ticks"] for row in rows], [100, 101, 102, 103])
        self.assertEqual(rows[0]["x_mm"], -120)
        self.assertEqual(rows[0]["position_sequence"], 7)
        self.assertEqual(rows[1]["accel_y_raw"], -200)
        self.assertEqual(rows[2]["gyro_scale_dps"], 2000)
        self.assertEqual(rows[3]["accel_x_raw"], 1)
        self.assertEqual(rows[1]["x_mm"], "")
        self.assertTrue(all(row["tag_serial"] == "01:00:05CD" for row in rows))
        self.assertTrue(all(row["packet_sequence"] == 42 for row in rows))

    def test_multiple_tags_filtering_and_imu_without_position(self):
        first = self.packet("01:00:0173", [
            cdp.MPUGyroscopeV2(x=1, y=2, z=3, gnt=9, scale=250, dlpf=5),
        ])
        second = self.packet("01:00:05CD", [
            cdp.PositionV1(x=10, y=20, z=30, gnt=10),
        ])
        rows = list(rows_from_packet(first, "now")) + list(rows_from_packet(second, "now"))
        self.assertEqual([row["tag_serial"] for row in rows],
                         ["01:00:0173", "01:00:05CD"])
        self.assertEqual(rows[0]["item_type"], "gyroscope")
        self.assertEqual(rows[0]["x_mm"], "")
        self.assertEqual(list(rows_from_packet(first, "now", {"01:00:05CD"})), [])


if __name__ == "__main__":
    unittest.main()
