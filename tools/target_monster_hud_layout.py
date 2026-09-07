"""Shared data layout for the profiled 2025-07-16 target HUD."""


def make_layout(width, height, base=0):
    bmp_size = 122 + width * height * 4
    stride = (bmp_size + 15) & ~15
    buffers = base + 0x11000
    info_db = buffers + 6 * stride
    info_rows = info_db + 512 * 256
    current = info_rows + 384
    hp_text = current + 32
    numbers = hp_text + 64
    icon_state = numbers + 64
    options = icon_state + 32
    icon_path = options + 16
    element_row = icon_path + 256
    constants = element_row + 160
    return {
        'bmp_size': bmp_size, 'buffer_stride': stride, 'buffers': buffers,
        'info_db': info_db, 'info_rows': info_rows, 'current': current,
        'hp_text': hp_text, 'number_buffers': numbers, 'icon_state': icon_state,
        'options': options, 'icon_path': icon_path, 'element_row': element_row,
        'constants': constants, 'allocation_size': constants - base + 4096,
    }
