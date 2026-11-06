/* Home Dojo catalog: character options and room items.
 * Shared by the browser (window.CATALOG) and the server (require), so both
 * agree on what exists and when room items unlock. */
(function (root) {
  const CATALOG = {
    // Character maker. Every option is free.
    avatar: {
      skin: [
        { id: 's1', color: '#ffe3cc' }, { id: 's2', color: '#f7cba6' }, { id: 's3', color: '#e2a878' },
        { id: 's4', color: '#c4855a' }, { id: 's5', color: '#94603e' }, { id: 's6', color: '#5e3b25' },
      ],
      hairStyle: [
        { id: 'short' }, { id: 'bob' }, { id: 'long' }, { id: 'pigtails' },
        { id: 'ponytail' }, { id: 'bun' }, { id: 'curly' },
      ],
      hairColor: [
        { id: 'black', color: '#2b1d16' }, { id: 'brown', color: '#6b3f22' }, { id: 'auburn', color: '#a4502a' },
        { id: 'blonde', color: '#eac46a' }, { id: 'ginger', color: '#de7a2e' }, { id: 'pink', color: '#ff8fc8' },
        { id: 'purple', color: '#9b6bff' }, { id: 'blue', color: '#4fa3ff' },
      ],
      eyes: [{ id: 'round' }, { id: 'happy' }, { id: 'sparkle' }, { id: 'wink' }],
      mouth: [{ id: 'smile' }, { id: 'grin' }, { id: 'open' }, { id: 'tongue' }],
      outfit: [{ id: 'dress' }, { id: 'tee' }, { id: 'overalls' }, { id: 'hoodie' }],
      outfitColor: [
        { id: 'pink', color: '#ff6fa8' }, { id: 'purple', color: '#7c5cff' }, { id: 'red', color: '#f25454' },
        { id: 'orange', color: '#ff9f1c' }, { id: 'yellow', color: '#f5c518' }, { id: 'green', color: '#22b07d' },
        { id: 'blue', color: '#3b82f6' }, { id: 'teal', color: '#14b8b8' },
      ],
      accessory: [
        { id: 'none' }, { id: 'bow' }, { id: 'crown' }, { id: 'glasses' },
        { id: 'flower' }, { id: 'catears' }, { id: 'headband' },
      ],
    },

    // Room paint. Free.
    walls: [
      { id: 'cream', color: '#fdf1dc' }, { id: 'pink', color: '#ffd9e6' }, { id: 'lilac', color: '#e6dcff' },
      { id: 'sky', color: '#d6ebff' }, { id: 'mint', color: '#d5f5e6' }, { id: 'sun', color: '#fff1b8' },
    ],
    floors: [
      { id: 'wood', color: '#d9a46c' }, { id: 'pinkcarpet', color: '#f7a8c4' },
      { id: 'bluecarpet', color: '#9cc3f2' }, { id: 'checker', color: '#e8e1f5' }, { id: 'grass', color: '#8fd18a' },
    ],

    // Room items. `unlock` = all-time stars earned needed. `size` = width as % of the room.
    // `spot` = where it lands when first added (x, y of its bottom centre, in %).
    // `art` is a drawing in play.js, or `emoji` is shown instead. `layer: 'floor'` sits under everything.
    items: [
      { id: 'bed', name: 'Bed', art: 'bed', size: 34, unlock: 0, spot: [24, 90] },
      { id: 'rug', name: 'Rug', art: 'rug', size: 36, unlock: 0, layer: 'floor', spot: [56, 97] },
      { id: 'lamp', name: 'Lamp', art: 'lamp', size: 9, unlock: 0, spot: [7, 71] },
      { id: 'teddy', name: 'Teddy bear', emoji: '🧸', size: 9, unlock: 0, spot: [36, 95] },
      { id: 'plant', name: 'Plant', emoji: '🪴', size: 9, unlock: 0, spot: [95, 71] },
      { id: 'picture', name: 'Picture', emoji: '🖼️', size: 10, unlock: 0, spot: [62, 40] },
      { id: 'dresser', name: 'Dresser', art: 'dresser', size: 20, unlock: 5, spot: [88, 70] },
      { id: 'doll', name: 'Doll', art: 'doll', size: 8, unlock: 5, spot: [46, 96] },
      { id: 'bookshelf', name: 'Bookshelf', art: 'bookshelf', size: 17, unlock: 10, spot: [71, 70] },
      { id: 'ball', name: 'Ball', emoji: '⚽', size: 7, unlock: 10, spot: [62, 99] },
      { id: 'tv', name: 'TV', art: 'tv', size: 24, unlock: 15, spot: [42, 70] },
      { id: 'game', name: 'Game system', art: 'console', size: 13, unlock: 20, spot: [30, 99] },
      { id: 'desk', name: 'Desk', art: 'desk', size: 26, unlock: 25, spot: [20, 72] },
      { id: 'paints', name: 'Paints', emoji: '🎨', size: 8, unlock: 25, spot: [82, 97] },
      { id: 'guitar', name: 'Guitar', emoji: '🎸', size: 10, unlock: 30, spot: [95, 92] },
      { id: 'beanbag', name: 'Beanbag', art: 'beanbag', size: 16, unlock: 35, spot: [77, 95] },
      { id: 'piano', name: 'Keyboard', emoji: '🎹', size: 14, unlock: 40, spot: [56, 84] },
      { id: 'fishtank', name: 'Fish tank', art: 'fishtank', size: 18, unlock: 50, spot: [58, 70] },
      { id: 'puppy', name: 'Puppy', emoji: '🐶', size: 10, unlock: 60, spot: [68, 97] },
      { id: 'kitten', name: 'Kitten', emoji: '🐱', size: 9, unlock: 75, spot: [88, 98] },
      { id: 'castle', name: 'Play castle', emoji: '🏰', size: 18, unlock: 100, spot: [32, 82] },
      { id: 'unicorn', name: 'Unicorn', emoji: '🦄', size: 12, unlock: 125, spot: [12, 97] },
      { id: 'rocket', name: 'Rocket', emoji: '🚀', size: 12, unlock: 150, spot: [50, 88] },
    ],
  };

  CATALOG.defaultAvatar = (kidId, young) => ({
    skin: 's2',
    hairStyle: young ? 'pigtails' : 'long',
    hairColor: 'brown',
    eyes: 'round',
    mouth: 'smile',
    outfit: 'dress',
    outfitColor: kidId === 1 ? 'purple' : 'pink',
    accessory: young ? 'bow' : 'none',
  });

  CATALOG.defaultRoom = () => ({
    wall: 'cream',
    floor: 'wood',
    items: [{ id: 'bed', x: 26, y: 88 }, { id: 'rug', x: 56, y: 96 }],
    me: { x: 62, y: 86 },
  });

  if (typeof module !== 'undefined' && module.exports) module.exports = CATALOG;
  else root.CATALOG = CATALOG;
})(typeof window !== 'undefined' ? window : globalThis);
