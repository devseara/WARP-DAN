# BOH Fluent Emoji Assets

These PNGs are a 24x24 runtime copy of Microsoft's Fluent Emoji 3D set:

https://github.com/microsoft/fluentui-emoji

The QJS-only `FluentEmoji` patch copies them beside the patched client under:

`BohEmoji\fluent\`

`manifest.tsv` maps supported shortcode/raw-Unicode tokens to PNG filenames.
Canonical shortcodes use the Fluent filename without `_3d`, for example
`:red_heart:`, `:money_bag:`, and `:artist_dark:`.

NPC menus can use compact `@red_heart@` aliases because `:` is the option
separator. Raw Unicode aliases from `manifest.tsv` are also baked into the
patched executable at WARP time.

The upstream license text is kept in this folder as
`LICENSE.Microsoft-Fluent-Emoji.txt`.
