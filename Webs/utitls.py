# Code By @V_Sbotmaker (on Telegram)


def cp_list(existing_list, add_above: int = 0) -> list:
  try:
    return complete_sequence_fast(existing_list, add_above)
  except Exception:
    return existing_list

def complete_sequence_fast(existing_list, add_above: int = 1) -> list:
  nums = [float(x) for x in existing_list]


  max_val = max(nums)
  min_val = min(nums)


  sorted_nums = sorted(nums)
  increment = min(sorted_nums[i+1] - sorted_nums[i] 
                 for i in range(len(sorted_nums)-1) 
                 if sorted_nums[i+1] > sorted_nums[i])


  full_sequence = []
  if add_above > 0:
      for i in range(1, add_above + 1):
          val = max_val + i * increment
          if val.is_integer():
              full_sequence.append(int(val))
          else:
              full_sequence.append(val)


  steps = int((max_val - min_val) / increment) + 1
  for i in range(steps):
      val = max_val - i * increment
      if val.is_integer():
          full_sequence.append(int(val))
      else:
          full_sequence.append(val)


  if min_val > 1:
      remaining_steps = int((min_val - 1) / increment)
      for i in range(1, remaining_steps + 1):
          val = min_val - i * increment
          if val.is_integer():
              full_sequence.append(int(val))
          else:
              full_sequence.append(val)

  return full_sequence


BYPASS_URL = "https://api.shanksytprem.workers.dev/proxy?url={}"
BYPASS_URL_2 = "https://holy-pine-67c9.justatestsubject-01.workers.dev/proxy?url={}"
BYPASS_URL_3 = "https://holy-credit-da93.lajosip431.workers.dev/proxy?url={}"


DEAULT_MSG_FORMAT = """
<blockquote><b>{title}</b></blockquote>

**Status**: `{status}`
**Genres**: `{genres}`

**Description**: <blockquote expandable><i>{summary}...</i></blockquote>

**<a href={url}>Read More</a>**
"""


T_MSG_FORMAT = """<blockquote><b>{title}</b></blockquote>

**Status**: `{status}`
**Genres**: `{genres}`
**Language**: `{language}`

**Description**: <blockquote expandable><i>{summary}...</i></blockquote>

**<a href={url}>Read More</a>**
"""


ALL_MSG_FORMAT = """<blockquote expandable><b>{title}</b>

<b>Alt Title</b>: <i>{alt_title}</i></blockquote>

<blockquote expandable><b>Type</b>: <i>{type}</i>
<b>Status</b>: <i>{status}</i>
<b>Genres</b>: <i>{genres}</i>
<b>Year</b>: <i>{year}</i></blockquote>

<blockquote expandable><b>Description</b>: <i>{summary}...</i></blockquote>

**=> <a href={url}>Read More</a>**
**=> <a href={anilist}>AniList</a>**
**=> <a href={myanime}>MyAnimeList</a>**
"""

BALL_MSG_FORMAT = """<blockquote expandable><b>{title}</b>

<b>Alt Title</b>: <i>{alt_title}</i></blockquote>

<blockquote expandable><b>Status</b>: <i>{status}</i>
<b>Genres</b>: <i>{genres}</i>
<b>Rating</b>: <i>{rating}</i>
<b>Year</b>: <i>{year}</i></blockquote>

<blockquote expandable><b>Description</b>: <i>{summary}...</i></blockquote>

**=> <a href={url}>Read More</a>**
"""

ATSU_MSG_FORMAT = """<blockquote expandable><b>{title}</b>

<b>Alt Title</b>: <i>{alt_title}</i></blockquote>

<blockquote expandable><b>Genres</b>: <i>{genres}</i>
<b>Type</b>: <i>{type}</i>
<b>Status</b>: <i>{status}</i></blockquote>

<blockquote expandable><b>Description</b>: <i>{summary}...</i></blockquote>

**=> <a href={url}>Read More</a>**"""
