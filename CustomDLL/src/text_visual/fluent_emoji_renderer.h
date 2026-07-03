#pragma once

#include <windows.h>
#include <objidl.h>
#include <gdiplus.h>

#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#pragma comment(lib, "gdiplus.lib")

namespace BohFluentEmoji
{
typedef BOOL (WINAPI *TextOutW_t)(HDC, int, int, LPCWSTR, int);
typedef BOOL (WINAPI *GetTextExtentPoint32W_t)(HDC, LPCWSTR, int, LPSIZE);

struct EmojiSpec
{
	std::wstring token;
	std::wstring file;
	bool compact;
};

struct Segment
{
	bool emoji;
	std::wstring text;
	std::wstring file;
	bool compact;
};

static HMODULE g_module = nullptr;
static ULONG_PTR g_gdiplusToken = 0;
static bool g_gdiplusStarted = false;
static bool g_manifestLoaded = false;
static std::mutex g_mutex;
static std::vector<EmojiSpec> g_specs;
static std::unordered_map<std::wstring, std::unique_ptr<Gdiplus::Image>> g_images;
static std::unordered_map<std::wstring, bool> g_fileExists;

static const wchar_t* const kFallbackSpecs[][2] =
{
	{L":heart:", L"red_heart.png"},
	{L"\x2764\xFE0F", L"red_heart.png"},
	{L"\x2764", L"red_heart.png"},

	{L":warning:", L"warning.png"},
	{L":warn:", L"warning.png"},
	{L"\x26A0\xFE0F", L"warning.png"},
	{L"\x26A0", L"warning.png"},

	{L":check:", L"check_mark_button.png"},
	{L":ok:", L"check_mark_button.png"},
	{L"\x2705", L"check_mark_button.png"},

	{L":x:", L"cross_mark.png"},
	{L":cross:", L"cross_mark.png"},
	{L"\x274C", L"cross_mark.png"},

	{L":coin:", L"coin.png"},
	{L"\xD83E\xDE99", L"coin.png"},

	{L":money:", L"money_bag.png"},
	{L":zeny:", L"money_bag.png"},
	{L"\xD83D\xDCB0", L"money_bag.png"},

	{L":gem:", L"gem_stone.png"},
	{L"\xD83D\xDC8E", L"gem_stone.png"},

	{L":shield:", L"shield.png"},
	{L"\xD83D\xDEE1\xFE0F", L"shield.png"},
	{L"\xD83D\xDEE1", L"shield.png"},

	{L":swords:", L"crossed_swords.png"},
	{L":sword:", L"crossed_swords.png"},
	{L"\x2694\xFE0F", L"crossed_swords.png"},
	{L"\x2694", L"crossed_swords.png"},

	{L":smile:", L"smiling_face_with_smiling_eyes.png"},
	{L"\xD83D\xDE0A", L"smiling_face_with_smiling_eyes.png"},

	{L":fire:", L"fire.png"},
	{L"\xD83D\xDD25", L"fire.png"},

	{L":sparkles:", L"sparkles.png"},
	{L"\x2728", L"sparkles.png"},

	{L":star:", L"star.png"},
	{L"\x2B50", L"star.png"},

	{L":crown:", L"crown.png"},
	{L"\xD83D\xDC51", L"crown.png"},
};

static void SetModule(HMODULE module)
{
	if (module)
		g_module = module;
}

static std::wstring ModuleDirectory()
{
	wchar_t path[MAX_PATH] = {};
	if (g_module)
		GetModuleFileNameW(g_module, path, MAX_PATH);
	else
		GetModuleFileNameW(nullptr, path, MAX_PATH);

	std::wstring result(path);
	const size_t slash = result.find_last_of(L"\\/");
	if (slash != std::wstring::npos)
		result.resize(slash);
	return result;
}

static std::wstring AssetPath(const std::wstring& file)
{
	return ModuleDirectory() + L"\\BohEmoji\\fluent\\" + file;
}

static std::wstring ManifestPath()
{
	return ModuleDirectory() + L"\\BohEmoji\\fluent\\manifest.tsv";
}

static bool ReadUtf8File(const std::wstring& path, std::wstring& out)
{
	HANDLE file = CreateFileW(
		path.c_str(),
		GENERIC_READ,
		FILE_SHARE_READ,
		nullptr,
		OPEN_EXISTING,
		FILE_ATTRIBUTE_NORMAL,
		nullptr);
	if (file == INVALID_HANDLE_VALUE)
		return false;

	DWORD size = GetFileSize(file, nullptr);
	if (size == INVALID_FILE_SIZE)
	{
		CloseHandle(file);
		return false;
	}

	std::string bytes;
	bytes.resize(size);
	DWORD read = 0;
	const BOOL ok = size == 0 ||
		ReadFile(file, &bytes[0], size, &read, nullptr);
	CloseHandle(file);
	if (!ok || read != size)
		return false;

	if (bytes.empty())
	{
		out.clear();
		return true;
	}

	int chars = MultiByteToWideChar(
		CP_UTF8,
		0,
		bytes.data(),
		static_cast<int>(bytes.size()),
		nullptr,
		0);
	if (chars <= 0)
		return false;

	out.resize(chars);
	MultiByteToWideChar(
		CP_UTF8,
		0,
		bytes.data(),
		static_cast<int>(bytes.size()),
		&out[0],
		chars);

	if (!out.empty() && out[0] == 0xFEFF)
		out.erase(0, 1);
	return true;
}

static void AddSpecLocked(const std::wstring& token, const std::wstring& file)
{
	if (token.empty() || file.empty())
		return;

	if (token[0] == L':' ||
	    token[0] == L'@')
		g_specs.push_back(EmojiSpec{token, file, token[0] == L'@'});

	if (token.length() > 2 &&
	    token[0] == L':' &&
	    token[token.length() - 1] == L':')
	{
		std::wstring menuToken = L"@" + token.substr(1, token.length() - 2) + L"@";
		g_specs.push_back(EmojiSpec{menuToken, file, true});
	}
}

static void LoadManifestLocked()
{
	if (g_manifestLoaded)
		return;

	std::wstring manifest;
	if (ReadUtf8File(ManifestPath(), manifest))
	{
		size_t lineStart = 0;
		while (lineStart <= manifest.length())
		{
			size_t lineEnd = manifest.find_first_of(L"\r\n", lineStart);
			if (lineEnd == std::wstring::npos)
				lineEnd = manifest.length();

			std::wstring line = manifest.substr(lineStart, lineEnd - lineStart);
			if (!line.empty() && line[0] != L'#')
			{
				const size_t tab = line.find(L'\t');
				if (tab != std::wstring::npos)
					AddSpecLocked(line.substr(0, tab), line.substr(tab + 1));
			}

			if (lineEnd >= manifest.length())
				break;
			lineStart = lineEnd + 1;
			if (lineStart < manifest.length() &&
			    manifest[lineEnd] == L'\r' &&
			    manifest[lineStart] == L'\n')
				++lineStart;
		}
	}

	for (const auto& spec : kFallbackSpecs)
		AddSpecLocked(spec[0], spec[1]);

	g_manifestLoaded = true;
}

static void EnsureSpecsLoaded()
{
	if (g_manifestLoaded)
		return;

	std::lock_guard<std::mutex> lock(g_mutex);
	LoadManifestLocked();
}

static bool EnsureGdiplus()
{
	if (g_gdiplusStarted)
		return true;

	Gdiplus::GdiplusStartupInput input;
	if (Gdiplus::GdiplusStartup(&g_gdiplusToken, &input, nullptr) != Gdiplus::Ok)
		return false;

	g_gdiplusStarted = true;
	return true;
}

static bool AssetExists(const std::wstring& file)
{
	std::lock_guard<std::mutex> lock(g_mutex);
	const auto found = g_fileExists.find(file);
	if (found != g_fileExists.end())
		return found->second;

	const bool exists = GetFileAttributesW(AssetPath(file).c_str()) != INVALID_FILE_ATTRIBUTES;
	g_fileExists[file] = exists;
	return exists;
}

static Gdiplus::Image* LoadImage(const std::wstring& file)
{
	std::lock_guard<std::mutex> lock(g_mutex);
	auto found = g_images.find(file);
	if (found != g_images.end())
		return found->second.get();

	if (!EnsureGdiplus())
		return nullptr;

	std::unique_ptr<Gdiplus::Image> image(new Gdiplus::Image(AssetPath(file).c_str()));
	if (!image || image->GetLastStatus() != Gdiplus::Ok)
		return nullptr;

	Gdiplus::Image* raw = image.get();
	g_images[file] = std::move(image);
	return raw;
}

static bool PotentialTokenStart(wchar_t ch)
{
	return ch == L':' || ch == L'@';
}

static bool StartsWith(const std::wstring& text, size_t at, const std::wstring& token)
{
	return at + token.length() <= text.length() &&
	       text.compare(at, token.length(), token) == 0;
}

static bool MatchAt(
	const std::wstring& text,
	size_t at,
	std::wstring& file,
	bool& compact,
	size_t& tokenLen)
{
	EnsureSpecsLoaded();

	const EmojiSpec* best = nullptr;
	size_t bestLen = 0;

	for (const EmojiSpec& candidate : g_specs)
	{
		const size_t len = candidate.token.length();
		if (len <= bestLen)
			continue;
		if (StartsWith(text, at, candidate.token))
		{
			if (!AssetExists(candidate.file))
				continue;
			best = &candidate;
			bestLen = len;
		}
	}

	if (!best)
		return false;

	file = best->file;
	compact = best->compact;
	tokenLen = bestLen;
	return true;
}

static std::vector<Segment> SegmentText(const std::wstring& text)
{
	std::vector<Segment> segments;
	size_t runStart = 0;
	for (size_t i = 0; i < text.length(); )
	{
		std::wstring file;
		bool compact = false;
		size_t tokenLen = 0;
		if (PotentialTokenStart(text[i]) && MatchAt(text, i, file, compact, tokenLen))
		{
			if (i > runStart)
				segments.push_back(Segment{false, text.substr(runStart, i - runStart), L"", false});
			segments.push_back(Segment{true, L"", file, compact});
			i += tokenLen;
			runStart = i;
			continue;
		}
		++i;
	}

	if (runStart < text.length())
		segments.push_back(Segment{false, text.substr(runStart), L"", false});

	return segments;
}

static bool HasEmoji(const std::wstring& text)
{
	for (size_t i = 0; i < text.length(); ++i)
	{
		if (!PotentialTokenStart(text[i]))
			continue;

		std::wstring file;
		bool compact = false;
		size_t tokenLen = 0;
		if (MatchAt(text, i, file, compact, tokenLen))
			return true;
	}
	return false;
}

static int EmojiSize(HDC hdc, bool compact)
{
	if (!compact)
		return 24;

	TEXTMETRICW tm = {};
	if (!GetTextMetricsW(hdc, &tm))
		return 14;

	int size = tm.tmHeight;
	if (size < 10)
		size = 10;
	if (size > 16)
		size = 16;
	return size;
}

static int IconTop(HDC hdc, int y, int icon)
{
	TEXTMETRICW tm = {};
	GetTextMetricsW(hdc, &tm);
	const UINT align = GetTextAlign(hdc);
	int textTop = y;
	if ((align & TA_BASELINE) == TA_BASELINE)
		textTop = y - tm.tmAscent;
	else if ((align & TA_BOTTOM) == TA_BOTTOM)
		textTop = y - tm.tmHeight;
	return textTop + ((tm.tmHeight - icon) / 2);
}

static bool Measure(HDC hdc, const std::wstring& text, GetTextExtentPoint32W_t getExtent, SIZE* size)
{
	if (!size || !getExtent || !HasEmoji(text))
		return false;

	const std::vector<Segment> segments = SegmentText(text);
	if (segments.empty())
		return false;

	SIZE total = {};

	for (const Segment& segment : segments)
	{
		if (segment.emoji)
		{
			const int icon = EmojiSize(hdc, segment.compact);
			total.cx += icon;
			if (icon > total.cy)
				total.cy = icon;
			continue;
		}

		if (segment.text.empty())
			continue;

		SIZE part = {};
		if (!getExtent(hdc, segment.text.c_str(), static_cast<int>(segment.text.length()), &part))
			return false;
		total.cx += part.cx;
		if (part.cy > total.cy)
			total.cy = part.cy;
	}

	if (total.cy == 0)
		total.cy = EmojiSize(hdc, false);

	*size = total;
	return true;
}

static bool Draw(HDC hdc, int x, int y, const std::wstring& text,
                 TextOutW_t textOut, GetTextExtentPoint32W_t getExtent,
                 bool skipImages, BOOL* result)
{
	if (!result || !textOut || !getExtent || !HasEmoji(text))
		return false;

	const std::vector<Segment> segments = SegmentText(text);
	if (segments.empty())
		return false;

	if (!skipImages)
	{
		for (const Segment& segment : segments)
		{
			if (segment.emoji && !LoadImage(segment.file))
				return false;
		}
	}

	SIZE total = {};
	Measure(hdc, text, getExtent, &total);

	const UINT oldAlign = GetTextAlign(hdc);
	int drawX = x;
	if ((oldAlign & TA_CENTER) == TA_CENTER)
		drawX -= total.cx / 2;
	else if ((oldAlign & TA_RIGHT) == TA_RIGHT)
		drawX -= total.cx;

	BOOL ok = TRUE;

	int saved = SaveDC(hdc);
	SetTextAlign(hdc, (oldAlign & ~(TA_CENTER | TA_RIGHT | TA_UPDATECP)) | TA_LEFT);

	for (const Segment& segment : segments)
	{
		if (segment.emoji)
		{
			const int icon = EmojiSize(hdc, segment.compact);
			const int top = IconTop(hdc, y, icon);
			if (!skipImages)
			{
				Gdiplus::Image* image = LoadImage(segment.file);
				if (image)
				{
					Gdiplus::Graphics graphics(hdc);
					graphics.SetInterpolationMode(Gdiplus::InterpolationModeNearestNeighbor);
					graphics.DrawImage(image, drawX, top, icon, icon);
				}
			}
			drawX += icon;
			continue;
		}

		if (segment.text.empty())
			continue;

		if (!textOut(hdc, drawX, y, segment.text.c_str(), static_cast<int>(segment.text.length())))
			ok = FALSE;

		SIZE part = {};
		if (getExtent(hdc, segment.text.c_str(), static_cast<int>(segment.text.length()), &part))
			drawX += part.cx;
	}

	if (saved)
		RestoreDC(hdc, saved);

	*result = ok;
	return true;
}

static void Cleanup()
{
	std::lock_guard<std::mutex> lock(g_mutex);
	g_images.clear();
	g_fileExists.clear();
	g_specs.clear();
	g_manifestLoaded = false;
	if (g_gdiplusStarted)
	{
		Gdiplus::GdiplusShutdown(g_gdiplusToken);
		g_gdiplusToken = 0;
		g_gdiplusStarted = false;
	}
}
}
