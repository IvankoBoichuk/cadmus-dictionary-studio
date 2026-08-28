import { useState, type SyntheticEvent } from "react";

import {
  dictionaryPageImageUrl,
  type EntryFieldResponse,
  type EntryFragmentResponse,
} from "../api";

type Size = { width: number; height: number };
type Box = { x: number; y: number; width: number; height: number };

const CROP_CONTEXT_PADDING_RATIO = 0.2;
const CROP_MIN_PADDING = 40;

function fragmentBoxes(fragment: EntryFragmentResponse): Box[] {
  const boxes: Box[] = [
    { x: fragment.x, y: fragment.y, width: fragment.width, height: fragment.height },
  ];
  if (
    fragment.x2 != null &&
    fragment.y2 != null &&
    fragment.width2 != null &&
    fragment.height2 != null
  ) {
    boxes.push({
      x: fragment.x2,
      y: fragment.y2,
      width: fragment.width2,
      height: fragment.height2,
    });
  }
  return boxes;
}

/** Shared crop-math primitive: a zoomed-in view of one page's image around
 * a padded union of `boxes`, with each box outlined. Used both for a whole
 * fragment (BH-148) and for one field's own geometry (BH-148 ALTO
 * segmentation, experimental variant 1). */
function PageRegionCrop({
  dictionaryId,
  pageNumber,
  boxes,
  alt,
  displayWidth = 480,
}: {
  dictionaryId: string;
  pageNumber: number;
  boxes: Box[];
  alt: string;
  displayWidth?: number;
}) {
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);

  const minX = Math.min(...boxes.map((box) => box.x));
  const minY = Math.min(...boxes.map((box) => box.y));
  const maxX = Math.max(...boxes.map((box) => box.x + box.width));
  const maxY = Math.max(...boxes.map((box) => box.y + box.height));
  const padding =
    Math.max(maxX - minX, maxY - minY) * CROP_CONTEXT_PADDING_RATIO || CROP_MIN_PADDING;

  const cropX = Math.max(0, minX - padding);
  const cropY = Math.max(0, minY - padding);
  const cropWidth = maxX - minX + padding * 2;
  const cropHeight = maxY - minY + padding * 2;
  const scale = cropWidth > 0 ? displayWidth / cropWidth : 1;
  const displayHeight = cropHeight * scale;

  const handleLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
  };

  return (
    <div
      className="entry-fragment-crop"
      style={{ width: displayWidth, height: displayHeight }}
    >
      <img
        className="entry-fragment-crop-image"
        src={dictionaryPageImageUrl(dictionaryId, pageNumber)}
        alt={alt}
        draggable={false}
        onLoad={handleLoad}
        style={{
          left: -cropX * scale,
          top: -cropY * scale,
          width: naturalSize ? naturalSize.width * scale : undefined,
          height: naturalSize ? naturalSize.height * scale : undefined,
        }}
      />
      {boxes.map((box) => (
        <div
          key={`${box.x}-${box.y}`}
          className="entry-fragment-crop-box"
          style={{
            left: (box.x - cropX) * scale,
            top: (box.y - cropY) * scale,
            width: box.width * scale,
            height: box.height * scale,
          }}
        />
      ))}
    </div>
  );
}

/** BH-148: a zoomed-in crop of the source page around one entry fragment,
 * so an editor can see exactly how the article was printed while filling
 * in its fields. */
export function EntryFragmentCrop({
  dictionaryId,
  fragment,
}: {
  dictionaryId: string;
  fragment: EntryFragmentResponse;
}) {
  if (fragment.page_number == null) {
    return (
      <p className="lede">
        Не вдалося визначити сторінку джерела для цього фрагмента.
      </p>
    );
  }
  return (
    <PageRegionCrop
      dictionaryId={dictionaryId}
      pageNumber={fragment.page_number}
      boxes={fragmentBoxes(fragment)}
      alt={`Скан сторінки ${fragment.page_number}: «${fragment.recognized_text}»`}
    />
  );
}

/** BH-148 ALTO segmentation (experimental variant 1): a small crop around
 * one field's own bounding box (the union of the OCR word segments it was
 * extracted from), so an editor can confirm exactly where on the page a
 * field came from -- not just which fragment. Renders nothing for fields
 * without geometry (e.g. manually added ones, or ones from the flat-text
 * extraction path). */
export function EntryFieldCrop({
  dictionaryId,
  pageNumber,
  field,
}: {
  dictionaryId: string;
  pageNumber: number | null;
  field: EntryFieldResponse;
}) {
  if (
    pageNumber == null ||
    field.x == null ||
    field.y == null ||
    field.width == null ||
    field.height == null
  ) {
    return null;
  }
  return (
    <PageRegionCrop
      dictionaryId={dictionaryId}
      pageNumber={pageNumber}
      boxes={[{ x: field.x, y: field.y, width: field.width, height: field.height }]}
      alt={`Розташування поля на сторінці: «${field.source_text}»`}
      displayWidth={220}
    />
  );
}
