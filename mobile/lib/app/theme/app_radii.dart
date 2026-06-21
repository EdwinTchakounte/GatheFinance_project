import 'package:flutter/material.dart';

/// Rayons utilisés à travers l'app — proche du langage iOS/Material 3 moderne.
class AppRadii {
  AppRadii._();

  static const r4 = Radius.circular(4);
  static const r8 = Radius.circular(8);
  static const r10 = Radius.circular(10);
  static const r12 = Radius.circular(12);
  static const r14 = Radius.circular(14); // default for cards (reduced)
  static const r16 = Radius.circular(16);
  static const r18 = Radius.circular(18); // hero / sheets (reduced)
  static const r20 = Radius.circular(20);
  static const r24 = Radius.circular(24);
  static const r28 = Radius.circular(28);
  static const pill = Radius.circular(9999);

  /// Cards courantes — radius 10 (encore réduit le 2026-06-18 itération 2).
  static const card = BorderRadius.all(r10);
  /// Hero balance — radius 14.
  static const cardHero = BorderRadius.all(r14);
  /// Bottom sheets — coin top 14.
  static const sheet = BorderRadius.vertical(top: r14);
  /// Boutons CTA — radius 10.
  static const button = BorderRadius.all(r10);
  /// Chips / pills compactes — radius 8.
  static const chip = BorderRadius.all(r8);
  /// Inputs / fields — radius 8.
  static const field = BorderRadius.all(r8);
}
