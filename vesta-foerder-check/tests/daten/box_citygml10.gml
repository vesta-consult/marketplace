<?xml version="1.0" encoding="UTF-8"?>
<!-- Synthetische Testdaten: zwei Quader 10 x 10 x 6 m, Abstand 40 m, keine echten Orte. -->
<core:CityModel xmlns:core="http://www.opengis.net/citygml/1.0" xmlns:bldg="http://www.opengis.net/citygml/building/1.0" xmlns:gen="http://www.opengis.net/citygml/generics/1.0" xmlns:gml="http://www.opengis.net/gml" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink">
  <gml:boundedBy>
    <gml:Envelope srsName="urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH" srsDimension="3">
      <gml:lowerCorner>500000.000 5400000.000 400.000</gml:lowerCorner>
      <gml:upperCorner>500060.000 5400010.000 406.000</gml:upperCorner>
    </gml:Envelope>
  </gml:boundedBy>
  <core:cityObjectMember>
    <bldg:Building gml:id="TEST_GEB_1">
      <gen:doubleAttribute name="HoeheGrund">
        <gen:value>400.00</gen:value>
      </gen:doubleAttribute>
      <bldg:function>31001_1000</bldg:function>
      <bldg:roofType>1000</bldg:roofType>
      <bldg:measuredHeight uom="urn:adv:uom:m">6.0</bldg:measuredHeight>
      <bldg:boundedBy>
        <bldg:GroundSurface gml:id="TEST_GEB_1_F0">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P0">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500000.000 5400000.000 400.000 500000.000 5400010.000 400.000 500010.000 5400010.000 400.000 500010.000 5400000.000 400.000 500000.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:GroundSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_1_F1">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P1">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500000.000 5400000.000 400.000 500010.000 5400000.000 400.000 500010.000 5400000.000 406.000 500000.000 5400000.000 406.000 500000.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_1_F2">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P2">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500010.000 5400000.000 400.000 500010.000 5400010.000 400.000 500010.000 5400010.000 406.000 500010.000 5400000.000 406.000 500010.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_1_F3">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P3">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500010.000 5400010.000 400.000 500000.000 5400010.000 400.000 500000.000 5400010.000 406.000 500010.000 5400010.000 406.000 500010.000 5400010.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_1_F4">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P4">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500000.000 5400010.000 400.000 500000.000 5400000.000 400.000 500000.000 5400000.000 406.000 500000.000 5400010.000 406.000 500000.000 5400010.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:RoofSurface gml:id="TEST_GEB_1_F5">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_1_P5">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500000.000 5400000.000 406.000 500010.000 5400000.000 406.000 500010.000 5400010.000 406.000 500000.000 5400010.000 406.000 500000.000 5400000.000 406.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:RoofSurface>
      </bldg:boundedBy>
      <bldg:address>
        <core:Address>
          <core:xalAddress>
            <xAL:AddressDetails>
              <xAL:Country>
                <xAL:CountryName>Germany</xAL:CountryName>
                <xAL:Locality Type="Town">
                  <xAL:LocalityName>Musterstadt</xAL:LocalityName>
                  <xAL:Thoroughfare Type="Street">
                    <xAL:ThoroughfareNumber>1</xAL:ThoroughfareNumber>
                    <xAL:ThoroughfareName>Musterweg</xAL:ThoroughfareName>
                  </xAL:Thoroughfare>
                </xAL:Locality>
              </xAL:Country>
            </xAL:AddressDetails>
          </core:xalAddress>
        </core:Address>
      </bldg:address>
    </bldg:Building>
  </core:cityObjectMember>
  <core:cityObjectMember>
    <bldg:Building gml:id="TEST_GEB_2">
      <gen:doubleAttribute name="HoeheGrund">
        <gen:value>400.00</gen:value>
      </gen:doubleAttribute>
      <bldg:function>31001_1000</bldg:function>
      <bldg:roofType>1000</bldg:roofType>
      <bldg:measuredHeight uom="urn:adv:uom:m">6.0</bldg:measuredHeight>
      <bldg:boundedBy>
        <bldg:GroundSurface gml:id="TEST_GEB_2_F0">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P0">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500050.000 5400000.000 400.000 500050.000 5400010.000 400.000 500060.000 5400010.000 400.000 500060.000 5400000.000 400.000 500050.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:GroundSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_2_F1">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P1">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500050.000 5400000.000 400.000 500060.000 5400000.000 400.000 500060.000 5400000.000 406.000 500050.000 5400000.000 406.000 500050.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_2_F2">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P2">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500060.000 5400000.000 400.000 500060.000 5400010.000 400.000 500060.000 5400010.000 406.000 500060.000 5400000.000 406.000 500060.000 5400000.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_2_F3">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P3">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500060.000 5400010.000 400.000 500050.000 5400010.000 400.000 500050.000 5400010.000 406.000 500060.000 5400010.000 406.000 500060.000 5400010.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="TEST_GEB_2_F4">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P4">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500050.000 5400010.000 400.000 500050.000 5400000.000 400.000 500050.000 5400000.000 406.000 500050.000 5400010.000 406.000 500050.000 5400010.000 400.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:RoofSurface gml:id="TEST_GEB_2_F5">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="TEST_GEB_2_P5">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList srsDimension="3">500050.000 5400000.000 406.000 500060.000 5400000.000 406.000 500060.000 5400010.000 406.000 500050.000 5400010.000 406.000 500050.000 5400000.000 406.000</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:RoofSurface>
      </bldg:boundedBy>
      <bldg:address>
        <core:Address>
          <core:xalAddress>
            <xAL:AddressDetails>
              <xAL:Country>
                <xAL:CountryName>Germany</xAL:CountryName>
                <xAL:Locality Type="Town">
                  <xAL:LocalityName>Musterstadt</xAL:LocalityName>
                  <xAL:Thoroughfare Type="Street">
                    <xAL:ThoroughfareNumber>7</xAL:ThoroughfareNumber>
                    <xAL:ThoroughfareName>Beispielgasse</xAL:ThoroughfareName>
                  </xAL:Thoroughfare>
                </xAL:Locality>
              </xAL:Country>
            </xAL:AddressDetails>
          </core:xalAddress>
        </core:Address>
      </bldg:address>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>
