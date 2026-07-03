#include "player_name_color/player_name_color.h"

#include "boh_features.h"
#include "extended_name/extended_name.h"

bool PlayerNameColorLookup(const std::wstring& text, COLORREF& color)
{
    color = CLR_INVALID;
#if BOH_PLAYER_NAME_COLORS
    return ExtendedNameLookupNameplateColor(text, color);
#else
    (void)text;
    return false;
#endif
}

